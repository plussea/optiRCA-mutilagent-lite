"""Tests for Critic Reviewer counterfactual challenges."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from optirc_lite.config import settings
from optirc_lite.skills.critic import RefactorCriticSkill
from optirc_lite.storage.evidence_graph import (
    EvidenceGraph,
    EvidenceNode,
    NodeType,
    EdgeType,
    EvidenceEdge,
)
from optirc_lite.tools.builtin import create_builtin_tools


@pytest.fixture
def temp_graph(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "evidence_graph.json"
        monkeypatch.setattr(settings, "evidence_graph_path", path)
        graph = EvidenceGraph(path=path)
        graph.init()
        yield graph


def _run_critic(graph: EvidenceGraph, candidates: list) -> dict:
    skill = RefactorCriticSkill()
    state = {
        "candidates": candidates,
        "evidence_graph": graph._read(),
    }
    output = asyncio.run(skill.run(state, create_builtin_tools()))
    return output["result"]


def _build_two_devices_one_link(graph: EvidenceGraph):
    """Two devices connected by a single link, each with a MUT_LOS alarm."""
    graph.add_node(EvidenceNode(id="dev:ne-a", type=NodeType.DEVICE, device_id="ne-a"))
    graph.add_node(EvidenceNode(id="dev:ne-b", type=NodeType.DEVICE, device_id="ne-b"))
    graph.add_node(EvidenceNode(id="port:ne-a:ab", type=NodeType.PORT, port_id="ne-a:ab", device_id="ne-a", direction="out"))
    graph.add_node(EvidenceNode(id="port:ne-b:ab", type=NodeType.PORT, port_id="ne-b:ab", device_id="ne-b", direction="in"))
    graph.add_node(EvidenceNode(id="link:ab", type=NodeType.LINK, link_id="ab", endpoint_a="ne-a:ab", endpoint_b="ne-b:ab", length_km=10.0))
    graph.add_node(EvidenceNode(id="alm:a", type=NodeType.ALARM, alarm_id="alm:a", alarm_type="MUT_LOS", severity="critical", timestamp="2026-08-03T10:00:00Z", device_id="ne-a"))
    graph.add_node(EvidenceNode(id="alm:b", type=NodeType.ALARM, alarm_id="alm:b", alarm_type="MUT_LOS", severity="critical", timestamp="2026-08-03T10:00:01Z", device_id="ne-b"))

    graph.add_edge(EvidenceEdge(source="dev:ne-a", target="port:ne-a:ab", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="dev:ne-b", target="port:ne-b:ab", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="port:ne-a:ab", target="link:ab", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="port:ne-b:ab", target="link:ab", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="alm:a", target="dev:ne-a", type=EdgeType.BELONGS_TO))
    graph.add_edge(EvidenceEdge(source="alm:b", target="dev:ne-b", type=EdgeType.BELONGS_TO))


def test_critic_passes_when_link_explains_all_alarms(temp_graph):
    _build_two_devices_one_link(temp_graph)
    candidates = [{
        "root_cause": "link:ab",
        "confidence": 0.9,
        "score_vector": [1.0, 0.9, 1.0, 1.0, 0.5, 1.0],
        "evidence_chain": ["candidate root cause: link:ab"],
    }]

    result = _run_critic(temp_graph, candidates)

    assert result["verdict"] == "pass"
    assert result["fallback_action"] is None


def test_critic_rejects_link_without_bidirectional_los(temp_graph):
    _build_two_devices_one_link(temp_graph)
    # Make endpoint B's alarm a non-LOS type.
    data = temp_graph._read()
    for node in data["nodes"]:
        if node["id"] == "alm:b":
            node["alarm_type"] = "LOW_OPTICAL_POWER"
    temp_graph._write(data)

    candidates = [{
        "root_cause": "link:ab",
        "confidence": 0.9,
        "score_vector": [1.0, 0.9, 1.0, 1.0, 0.5, 1.0],
        "evidence_chain": ["candidate root cause: link:ab"],
    }]

    result = _run_critic(temp_graph, candidates)

    assert result["verdict"] == "reject"
    assert result["fallback_action"] == "FALLBACK_TO_RANKER"
    assert any("bidirectional" in reason.lower() for reason in result["reasons"])


def test_critic_rejects_multi_cluster_not_explained(temp_graph):
    # Two disjoint device clusters, only one covered by the top candidate.
    graph = temp_graph
    graph.add_node(EvidenceNode(id="dev:ne-a", type=NodeType.DEVICE, device_id="ne-a"))
    graph.add_node(EvidenceNode(id="dev:ne-b", type=NodeType.DEVICE, device_id="ne-b"))
    graph.add_node(EvidenceNode(id="dev:ne-x", type=NodeType.DEVICE, device_id="ne-x"))
    graph.add_node(EvidenceNode(id="alm:a", type=NodeType.ALARM, alarm_id="alm:a", alarm_type="MUT_LOS", severity="critical", timestamp="2026-08-03T10:00:00Z", device_id="ne-a"))
    graph.add_node(EvidenceNode(id="alm:x", type=NodeType.ALARM, alarm_id="alm:x", alarm_type="MUT_LOS", severity="critical", timestamp="2026-08-03T10:00:02Z", device_id="ne-x"))

    graph.add_edge(EvidenceEdge(source="dev:ne-a", target="dev:ne-b", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="alm:a", target="dev:ne-a", type=EdgeType.BELONGS_TO))
    graph.add_edge(EvidenceEdge(source="alm:x", target="dev:ne-x", type=EdgeType.BELONGS_TO))

    candidates = [{
        "root_cause": "dev:ne-a",
        "confidence": 0.8,
        "score_vector": [0.5, 0.6, 0.5, 1.0, 0.5, 0.9],
        "evidence_chain": ["candidate root cause: dev:ne-a"],
    }]

    result = _run_critic(temp_graph, candidates)

    assert result["verdict"] == "reject"
    assert result["fallback_action"] == "FALLBACK_TO_JUDGE"
    assert any("cluster" in reason.lower() for reason in result["reasons"])


def test_critic_no_candidates_falls_back_to_judge(temp_graph):
    result = _run_critic(temp_graph, [])

    assert result["verdict"] == "reject"
    assert result["fallback_action"] == "FALLBACK_TO_JUDGE"
