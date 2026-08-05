"""Tests for Rank submodules: Feature Scorer and Rank Aggregator."""

import asyncio

import pytest

from optirc_lite.skills.rank import RootCauseRankerSkill
from optirc_lite.skills.rank.scorer import FeatureScorer, RankAggregator


def _make_candidate(root_cause: str, evidence_chain: list[str] | None = None) -> dict:
    return {
        "root_cause": root_cause,
        "confidence": 0.0,
        "score_vector": [],
        "evidence_chain": evidence_chain or [],
    }


def test_scorer_attaches_six_dimensional_vector():
    scorer = FeatureScorer()
    candidates = [
        _make_candidate("link:ab", ["candidate root cause: link:ab", "MUT_LOS @ OLT-A"]),
        _make_candidate("dev:olt-a", ["candidate root cause: dev:olt-a"]),
    ]
    state = {
        "perception": {"alarm_count": 1, "alarms": []},
        "evidence_graph": {"nodes": [], "edges": []},
    }
    scored = scorer.score(candidates, state)

    assert len(scored) == 2
    for candidate in scored:
        assert len(candidate["score_vector"]) == 6
        assert all(isinstance(v, (int, float)) for v in candidate["score_vector"])


def test_aggregator_sorts_by_confidence():
    aggregator = RankAggregator()
    candidates = [
        _make_candidate("dev:x"),
        _make_candidate("link:ab"),
    ]
    candidates[0]["score_vector"] = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    candidates[1]["score_vector"] = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]

    ranked = aggregator.aggregate(candidates)

    assert ranked[0]["root_cause"] == "link:ab"
    assert ranked[0]["confidence"] == 1.0
    assert ranked[1]["root_cause"] == "dev:x"
    assert ranked[1]["confidence"] == 0.5


def test_ranker_skill_output_shape():
    skill = RootCauseRankerSkill()
    state = {
        "perception": {"alarm_count": 0, "alarms": []},
        "evidence_graph": {"nodes": [], "edges": []},
        "judge": {
            "candidates": [
                _make_candidate("link:ab", ["candidate root cause: link:ab"]),
                _make_candidate("dev:olt-a", ["candidate root cause: dev:olt-a"]),
            ]
        },
    }
    output = asyncio.run(skill.run(state, None))

    assert "result" in output
    assert "candidates" in output["result"]
    assert output["next_suggestions"] == ["critic.diagnosis_critic"]
