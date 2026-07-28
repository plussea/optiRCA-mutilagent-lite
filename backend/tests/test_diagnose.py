"""Tests for POST /api/v1/diagnose."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from optirc_lite.api.main import app
from optirc_lite.storage.evidence_graph import EvidenceGraph


client = TestClient(app)


@pytest.fixture
def fiber_cut_alarm_csv():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "alarms.csv"
        path.write_text(
            "告警源,名称,定位信息,级别,时间\n"
            "OLT-A,MUT_LOS,核心机房-ODF-1,critical,2026-07-27T10:00:00Z\n"
            "OLT-B,MUT_LOS,汇聚机房-ODF-2,critical,2026-07-27T10:00:01Z\n",
            encoding="utf-8",
        )
        yield path


@pytest.fixture
def fiber_cut_topology_json():
    return {
        "devices": [
            {"device_id": "OLT-A", "type": "OLT"},
            {"device_id": "OLT-B", "type": "OLT"},
        ],
        "ports": [
            {"port_id": "OLT-A:1", "device_id": "OLT-A", "direction": "out"},
            {"port_id": "OLT-B:1", "device_id": "OLT-B", "direction": "in"},
        ],
        "links": [
            {"link_id": "A-B", "endpoint_a": "OLT-A:1", "endpoint_b": "OLT-B:1", "length_km": 10.5},
        ],
    }


def test_diagnose_success_returns_dossier(fiber_cut_alarm_csv, fiber_cut_topology_json, tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    with fiber_cut_alarm_csv.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(fiber_cut_topology_json, ensure_ascii=False)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "dossier_id" in body
    assert body["requires_human_review"] is False
    assert "root_cause" in body
    assert "evidence_chain" in body
    assert 0.0 <= body["confidence"] <= 1.0
    assert "input" in body
    assert "evidence_graph" in body
    assert "critic_verdict" in body


def test_diagnose_degrades_on_invalid_topology(fiber_cut_alarm_csv, tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    with fiber_cut_alarm_csv.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": "not-json"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["requires_human_review"] is True
    assert body["degradation_reason"] == "invalid_topology"


def test_diagnose_degrades_on_empty_alarms(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    with tempfile.TemporaryDirectory() as tmp:
        empty_csv = Path(tmp) / "empty.csv"
        empty_csv.write_text("告警源,名称,定位信息,级别,时间\n", encoding="utf-8")
        with empty_csv.open("rb") as f:
            response = client.post(
                "/api/v1/diagnose",
                files={"alarms": ("empty.csv", f, "text/csv")},
                data={"topology": json.dumps({"devices": [], "ports": [], "links": []}, ensure_ascii=False)},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["requires_human_review"] is True
    assert "degradation_reason" in body


def test_diagnose_fallback_exceeded_returns_degraded(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    # Two devices with alarms but no link; every device candidate leaves the other alarm unexplained.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "alarms.csv"
        path.write_text(
            "告警源,名称,定位信息,级别,时间\n"
            "NE-OTN-01,MUT_LOS,机房A,critical,2026-07-27T10:00:00Z\n"
            "NE-OTN-02,MUT_LOS,机房B,critical,2026-07-27T10:00:01Z\n",
            encoding="utf-8",
        )
        topology = {
            "devices": [
                {"device_id": "NE-OTN-01", "type": "OTN"},
                {"device_id": "NE-OTN-02", "type": "OTN"},
            ],
            "ports": [],
            "links": [],
        }
        with path.open("rb") as f:
            response = client.post(
                "/api/v1/diagnose",
                files={"alarms": ("alarms.csv", f, "text/csv")},
                data={"topology": json.dumps(topology, ensure_ascii=False)},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["requires_human_review"] is True
    assert body["degradation_reason"] == "max_fallback_exceeded"
    assert "dossier_id" in body
    assert "evidence_graph" in body
