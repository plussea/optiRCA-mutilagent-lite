"""Tests for LLM enrichment fallback paths."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from optirc_lite.config import settings
from optirc_lite.skills.critic import RefactorCriticSkill
from optirc_lite.skills.critic.llm_reviewer import LLMCounterfactualReviewer
from optirc_lite.skills.judge import PropagationJudgeSkill
from optirc_lite.skills.judge.enricher import LLMHypothesisEnricher
from optirc_lite.storage.evidence_graph import (
    EdgeType,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    NodeType,
)
from optirc_lite.tools.builtin import create_builtin_tools
from optirc_lite.tools.registry import ToolRegistry


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


def test_enricher_returns_candidates_when_llm_disabled(temp_graph):
    enricher = LLMHypothesisEnricher()
    candidates = [
        {
            "root_cause": "link:ab",
            "confidence": 0.8,
            "score_vector": [],
            "evidence_chain": ["candidate root cause: link:ab"],
        }
    ]
    state = {
        "perception": {"alarm_count": 2, "alarms": []},
        "evidence_graph": temp_graph._read(),
    }
    result = asyncio.run(enricher.enrich(candidates, state, create_builtin_tools()))
    assert result == candidates


def test_enricher_adjusts_confidence_when_llm_available(temp_graph):
    _build_two_devices_one_link(temp_graph)
    enricher = LLMHypothesisEnricher()
    candidates = [
        {
            "root_cause": "link:ab",
            "confidence": 0.8,
            "score_vector": [],
            "evidence_chain": ["candidate root cause: link:ab"],
        }
    ]
    state = {
        "perception": {"alarm_count": 2, "alarms": []},
        "evidence_graph": temp_graph._read(),
    }

    tools = create_builtin_tools()
    tools._tools["llm.generate_json"] = AsyncMock(
        return_value={
            "candidates": [{"root_cause": "link:ab", "confidence": 0.95, "reasoning": "strong evidence"}],
            "added": [],
            "removed": [],
        }
    )

    with patch("optirc_lite.tools.llm.llm_tool.enabled", return_value=True):
        result = asyncio.run(enricher.enrich(candidates, state, tools))

    assert result[0]["confidence"] == 0.95
    assert result[0]["llm_enriched"] is True


def test_critic_llm_reviewer_confirms_rejection(temp_graph):
    reviewer = LLMCounterfactualReviewer()
    state = {
        "perception": {"alarm_count": 2, "alarms": []},
        "evidence_graph": temp_graph._read(),
        "candidates": [{"root_cause": "link:ab", "confidence": 0.8}],
    }

    tools = create_builtin_tools()
    tools._tools["llm.generate_json"] = AsyncMock(
        return_value={
            "verdict": "reject",
            "reasons": ["LLM confirms unexplained alarms"],
            "fallback_action": "FALLBACK_TO_JUDGE",
            "llm_review_note": "No plausible propagation path covers all alarms.",
        }
    )

    with patch("optirc_lite.tools.llm.llm_tool.enabled", return_value=True):
        result = asyncio.run(
            reviewer.review(
                "reject",
                ["rule rejection"],
                "FALLBACK_TO_JUDGE",
                state,
                tools,
            )
        )

    assert result["verdict"] == "reject"
    assert result["fallback_action"] == "FALLBACK_TO_JUDGE"
    assert "LLM confirms" in result["reasons"][0]
    assert result["llm_review_note"]


def test_critic_llm_reviewer_uses_rule_fallback_on_error(temp_graph):
    reviewer = LLMCounterfactualReviewer()
    state = {
        "perception": {"alarm_count": 2, "alarms": []},
        "evidence_graph": temp_graph._read(),
        "candidates": [{"root_cause": "link:ab", "confidence": 0.8}],
    }

    tools = create_builtin_tools()
    tools._tools["llm.generate_json"] = AsyncMock(side_effect=RuntimeError("timeout"))

    with patch("optirc_lite.tools.llm.llm_tool.enabled", return_value=True):
        result = asyncio.run(
            reviewer.review(
                "reject",
                ["rule rejection"],
                "FALLBACK_TO_JUDGE",
                state,
                tools,
            )
        )

    assert result["verdict"] == "reject"
    assert result["reasons"] == ["rule rejection"]
    assert result["fallback_action"] == "FALLBACK_TO_JUDGE"
    assert result["llm_review_note"] is None
