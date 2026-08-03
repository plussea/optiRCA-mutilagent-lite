"""Tests for Case Archivist and GET /v1/dossier/{dossier_id}."""

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
            "OLT-A,MUT_LOS,核心机房-ODF-1,critical,2026-08-03T10:00:00Z\n"
            "OLT-B,MUT_LOS,汇聚机房-ODF-2,critical,2026-08-03T10:00:01Z\n",
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


def test_get_dossier_returns_five_layer_dossier(
    fiber_cut_alarm_csv, fiber_cut_topology_json, tmp_path, monkeypatch
):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    monkeypatch.setattr("optirc_lite.config.settings.lancedb_path", tmp_path / "lancedb")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    with fiber_cut_alarm_csv.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(fiber_cut_topology_json, ensure_ascii=False)},
        )

    assert response.status_code == 200
    body = response.json()
    dossier_id = body["dossier_id"]

    dossier_response = client.get(f"/v1/dossier/{dossier_id}")
    assert dossier_response.status_code == 200
    dossier = dossier_response.json()
    assert dossier["dossier_id"] == dossier_id
    assert "input_layer" in dossier
    assert "intermediate_layer" in dossier
    assert "output_layer" in dossier
    assert "feedback_layer" in dossier
    assert "metadata" in dossier
    assert dossier["input_layer"]["topology"] == fiber_cut_topology_json
    assert dossier["output_layer"]["root_cause"]["root_cause"] == "link:A-B"


def test_dossier_not_found_returns_404(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    response = client.get("/v1/dossier/DOES-NOT-EXIST")
    assert response.status_code == 404
