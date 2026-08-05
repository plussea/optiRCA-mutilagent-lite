"""Tests for Judge submodules: Generator and Validator."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from optirc_lite.config import settings
from optirc_lite.skills.judge import PropagationJudgeSkill
from optirc_lite.skills.judge.generator import ChainHypothesisGenerator
from optirc_lite.skills.judge.validator import ChainValidator
from optirc_lite.storage.evidence_graph import (
    EdgeType,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    NodeType,
)


@pytest.fixture
def temp_graph(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "evidence_graph.json"
        monkeypatch.setattr(settings, "evidence_graph_path", path)
        graph = EvidenceGraph(path=path)
        graph.init()
        yield graph


def _build_two_devices_one_link(graph: EvidenceGraph):
    graph.add_node(EvidenceNode(id="dev:ne-a", type=NodeType.DEVICE, device_id="ne-a"))
    graph.add_node(EvidenceNode(id="dev:ne-b", type=NodeType.DEVICE, device_id="ne-b"))
    graph.add_node(
        EvidenceNode(
            id="port:ne-a:ab",
            type=NodeType.PORT,
            port_id="ne-a:ab",
            device_id="ne-a",
            direction="out",
        )
    )
    graph.add_node(
        EvidenceNode(
            id="port:ne-b:ab",
            type=NodeType.PORT,
            port_id="ne-b:ab",
            device_id="ne-b",
            direction="in",
        )
    )
    graph.add_node(
        EvidenceNode(
            id="link:ab",
            type=NodeType.LINK,
            link_id="ab",
            endpoint_a="ne-a:ab",
            endpoint_b="ne-b:ab",
            length_km=10.0,
        )
    )
    graph.add_node(
        EvidenceNode(
            id="alm:a",
            type=NodeType.ALARM,
            alarm_id="alm:a",
            alarm_type="MUT_LOS",
            severity="critical",
            timestamp="2026-08-03T10:00:00Z",
            device_id="ne-a",
        )
    )
    graph.add_node(
        EvidenceNode(
            id="alm:b",
            type=NodeType.ALARM,
            alarm_id="alm:b",
            alarm_type="MUT_LOS",
            severity="critical",
            timestamp="2026-08-03T10:00:01Z",
            device_id="ne-b",
        )
    )

    graph.add_edge(EvidenceEdge(source="dev:ne-a", target="port:ne-a:ab", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="dev:ne-b", target="port:ne-b:ab", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="port:ne-a:ab", target="link:ab", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="port:ne-b:ab", target="link:ab", type=EdgeType.TOPOLOGY))
    graph.add_edge(EvidenceEdge(source="alm:a", target="dev:ne-a", type=EdgeType.BELONGS_TO))
    graph.add_edge(EvidenceEdge(source="alm:b", target="dev:ne-b", type=EdgeType.BELONGS_TO))


def test_generator_creates_link_and_device_candidates(temp_graph):
    _build_two_devices_one_link(temp_graph)
    generator = ChainHypothesisGenerator()
    state = {
        "perception": {"alarm_count": 2, "alarms": []},
        "evidence_graph": temp_graph._read(),
    }
    candidates = generator.generate(state)

    root_causes = {c["root_cause"] for c in candidates}
    assert "link:ab" in root_causes
    assert "dev:ne-a" in root_causes
    assert "dev:ne-b" in root_causes

    link_candidate = next(c for c in candidates if c["root_cause"] == "link:ab")
    assert link_candidate["confidence"] == 0.8
    assert any("MUT_LOS" in line for line in link_candidate["evidence_chain"])


def test_validator_passes_through_candidates(temp_graph):
    _build_two_devices_one_link(temp_graph)
    generator = ChainHypothesisGenerator()
    validator = ChainValidator()
    state = {
        "perception": {"alarm_count": 2, "alarms": []},
        "evidence_graph": temp_graph._read(),
    }
    raw = generator.generate(state)
    validated = validator.validate(raw, state)

    assert len(validated) == len(raw)
    assert all("validation" in c for c in validated)
    assert all(c["validation"]["direction_check"] for c in validated)


def test_judge_skill_output_shape(temp_graph):
    _build_two_devices_one_link(temp_graph)
    skill = PropagationJudgeSkill()
    state = {
        "perception": {"alarm_count": 2, "alarms": []},
        "evidence_graph": temp_graph._read(),
    }
    output = asyncio.run(skill.run(state, None))

    assert "result" in output
    assert "candidates" in output["result"]
    assert isinstance(output["result"]["candidates"], list)
    assert output["next_suggestions"] == ["rank.candidate_ranker"]
