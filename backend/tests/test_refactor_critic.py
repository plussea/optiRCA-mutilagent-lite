"""Tests for POST /v1/refactor/critic."""

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


def _get_judge_rank_body(sample_alarm_csv, sample_topology_json, tmp_path, monkeypatch):
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
    return response.json()


def test_critic_endpoint_returns_verdict(sample_alarm_csv, sample_topology_json, tmp_path, monkeypatch):
    judge_rank_body = _get_judge_rank_body(sample_alarm_csv, sample_topology_json, tmp_path, monkeypatch)

    response = client.post(
        "/v1/refactor/critic",
        json={
            "candidates": judge_rank_body["candidates"],
            "evidence_graph": judge_rank_body["evidence_graph"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reviewed"
    assert "verdict" in body
    assert body["verdict"] in {"pass", "reject"}
    assert "reasons" in body
    assert "fallback_action" in body


def test_critic_rejects_candidate_that_leaves_unexplained_alarms(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    # One device candidate cannot explain the alarm on the other device.
    evidence_graph_payload = {
        "nodes": [
            {"id": "dev:NE-OTN-01", "type": "Device", "device_id": "NE-OTN-01"},
            {"id": "dev:NE-OTN-02", "type": "Device", "device_id": "NE-OTN-02"},
            {"id": "alm:0001", "type": "Alarm", "alarm_id": "alm:0001", "alarm_type": "MUT_LOS", "severity": "critical", "device_id": "NE-OTN-01"},
            {"id": "alm:0002", "type": "Alarm", "alarm_id": "alm:0002", "alarm_type": "MUT_LOS", "severity": "critical", "device_id": "NE-OTN-02"},
        ],
        "edges": [
            {"source": "alm:0001", "target": "dev:NE-OTN-01", "type": "BELONGS_TO"},
            {"source": "alm:0002", "target": "dev:NE-OTN-02", "type": "BELONGS_TO"},
        ],
    }
    candidates = [
        {
            "root_cause": "dev:NE-OTN-01",
            "confidence": 0.9,
            "score_vector": [1.0, 0.5, 0.5, 1.0, 0.5, 0.9],
            "evidence_chain": ["candidate root cause: dev:NE-OTN-01", "MUT_LOS @ NE-OTN-01"],
        }
    ]

    response = client.post(
        "/v1/refactor/critic",
        json={
            "candidates": candidates,
            "evidence_graph": evidence_graph_payload,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reviewed"
    assert body["verdict"] == "reject"
    assert body["fallback_action"] == "FALLBACK_TO_JUDGE"
    assert any("unexplained" in reason.lower() for reason in body["reasons"])


def test_critic_degrades_after_max_fallbacks(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    # Two devices with alarms but no link; every device candidate leaves the other alarm unexplained.
    evidence_graph_payload = {
        "nodes": [
            {"id": "dev:NE-OTN-01", "type": "Device", "device_id": "NE-OTN-01"},
            {"id": "dev:NE-OTN-02", "type": "Device", "device_id": "NE-OTN-02"},
            {"id": "alm:0001", "type": "Alarm", "alarm_id": "alm:0001", "alarm_type": "MUT_LOS", "severity": "critical", "device_id": "NE-OTN-01"},
            {"id": "alm:0002", "type": "Alarm", "alarm_id": "alm:0002", "alarm_type": "MUT_LOS", "severity": "critical", "device_id": "NE-OTN-02"},
        ],
        "edges": [
            {"source": "alm:0001", "target": "dev:NE-OTN-01", "type": "BELONGS_TO"},
            {"source": "alm:0002", "target": "dev:NE-OTN-02", "type": "BELONGS_TO"},
        ],
    }
    candidates = [
        {
            "root_cause": "dev:NE-OTN-01",
            "confidence": 0.9,
            "score_vector": [1.0, 0.5, 0.5, 1.0, 0.5, 0.9],
            "evidence_chain": ["candidate root cause: dev:NE-OTN-01", "MUT_LOS @ NE-OTN-01"],
        }
    ]

    response = client.post(
        "/v1/refactor/critic",
        json={
            "candidates": candidates,
            "evidence_graph": evidence_graph_payload,
            "max_fallback_rounds": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["requires_human_review"] is True
    assert body["degradation_reason"] == "max_fallback_exceeded"
