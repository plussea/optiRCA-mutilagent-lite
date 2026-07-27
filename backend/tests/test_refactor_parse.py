"""Tests for POST /v1/refactor/parse."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from optirc_lite.api.main import app
from optirc_lite.storage.evidence_graph import EvidenceGraph, NodeType, EdgeType


client = TestClient(app)


@pytest.fixture
def sample_alarm_csv():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "alarms.csv"
        path.write_text("告警源,名称,定位信息,级别,时间\nNE-OTN-01,MUT_LOS,西城核心机房-ODF-12,critical,2026-07-27T10:00:00Z\nNE-OTN-02,MUT_LOS,西城核心机房-ODF-12,critical,2026-07-27T10:00:01Z\n", encoding="utf-8")
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


def test_parse_endpoint_returns_fact_table_and_evidence_graph(sample_alarm_csv, sample_topology_json, tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    with sample_alarm_csv.open("rb") as f:
        response = client.post(
            "/v1/refactor/parse",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(sample_topology_json, ensure_ascii=False)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "perceived"
    assert "fact_table" in body
    assert "evidence_graph" in body
    assert len(body["fact_table"]["alarms"]) == 2
    assert body["fact_table"]["alarm_count"] == 2


def test_parse_endpoint_populates_graph_node_types(sample_alarm_csv, sample_topology_json, tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    graph = EvidenceGraph(path=tmp_path / "evidence_graph.json")
    graph.init()

    with sample_alarm_csv.open("rb") as f:
        response = client.post(
            "/v1/refactor/parse",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(sample_topology_json, ensure_ascii=False)},
        )

    assert response.status_code == 200
    node_types = {n.type for n in graph.get_nodes()}
    assert NodeType.DEVICE in node_types
    assert NodeType.PORT in node_types
    assert NodeType.ALARM in node_types
    assert NodeType.LINK in node_types
    assert EdgeType.BELONGS_TO in {e.type for e in graph.get_edges()}
    assert EdgeType.TOPOLOGY in {e.type for e in graph.get_edges()}


def test_parse_endpoint_returns_degraded_on_bad_topology(sample_alarm_csv, tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    with sample_alarm_csv.open("rb") as f:
        response = client.post(
            "/v1/refactor/parse",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": "not-json"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["confidence"] == 0.0
    assert body["requires_human_review"] is True
    assert "degradation_reason" in body
