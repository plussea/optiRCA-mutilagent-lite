"""Tests for POST /v1/refactor/judge-rank."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from optirc_lite.api.main import app
from optirc_lite.storage.evidence_graph import EvidenceGraph


client = TestClient(app)


@pytest.fixture
def sample_alarm_csv():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "alarms.csv"
        path.write_text(
            "告警源,名称,定位信息,级别,时间\n"
            "NE-OTN-01,MUT_LOS,西城核心机房-ODF-12,critical,2026-07-27T10:00:00Z\n"
            "NE-OTN-02,MUT_LOS,西城核心机房-ODF-12,critical,2026-07-27T10:00:01Z\n",
            encoding="utf-8",
        )
        yield path


@pytest.fixture
def sample_topology_json():
    return {
        "devices": [
            {"device_id": "NE-OTN-01", "type": "OTN"},
            {"device_id": "NE-OTN-02", "type": "OTN"},
        ],
        "links": [
            {"link_id": "link:01-02", "endpoint_a": "port:NE-OTN-01:1", "endpoint_b": "port:NE-OTN-02:1"},
        ],
        "ports": [
            {"port_id": "port:NE-OTN-01:1", "device_id": "NE-OTN-01", "direction": "out"},
            {"port_id": "port:NE-OTN-02:1", "device_id": "NE-OTN-02", "direction": "in"},
        ],
    }


def test_judge_rank_returns_candidates_with_score_vector(sample_alarm_csv, sample_topology_json, tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    with sample_alarm_csv.open("rb") as f:
        parse_response = client.post(
            "/v1/refactor/parse",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(sample_topology_json, ensure_ascii=False)},
        )

    assert parse_response.status_code == 200
    parse_body = parse_response.json()

    response = client.post(
        "/v1/refactor/judge-rank",
        json={
            "fact_table": parse_body["fact_table"],
            "evidence_graph": parse_body["evidence_graph"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "judged"
    assert "candidates" in body
    assert len(body["candidates"]) >= 1

    candidate = body["candidates"][0]
    assert "score_vector" in candidate
    assert len(candidate["score_vector"]) == 6
    assert "evidence_chain" in candidate
    assert 0.0 <= candidate["confidence"] <= 1.0

    top3_root_causes = [c["root_cause"] for c in body["candidates"][:3]]
    assert any("link:01-02" in rc for rc in top3_root_causes)


def test_judge_rank_returns_degraded_on_empty_graph(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    response = client.post(
        "/v1/refactor/judge-rank",
        json={
            "fact_table": {"alarm_count": 0, "alarms": []},
            "evidence_graph": {"nodes": [], "edges": []},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["confidence"] == 0.0
    assert body["requires_human_review"] is True
    assert "degradation_reason" in body
