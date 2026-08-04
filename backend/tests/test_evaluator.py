"""Tests for Evaluator metrics and error attribution."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from optirc_lite.api.main import app
from optirc_lite.storage.evidence_graph import EvidenceGraph
from optirc_lite.storage.sqlite_store import store


client = TestClient(app)


@pytest.fixture
def success_dossier_id(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    monkeypatch.setattr("optirc_lite.config.settings.lancedb_path", tmp_path / "lancedb")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    csv_path = tmp_path / "alarms.csv"
    csv_path.write_text(
        "告警源,名称,定位信息,级别,时间\n"
        "OLT-A,MUT_LOS,核心机房-ODF-1,critical,2026-08-04T10:00:00Z\n"
        "OLT-B,MUT_LOS,汇聚机房-ODF-2,critical,2026-08-04T10:00:01Z\n",
        encoding="utf-8",
    )
    topology = {
        "devices": [{"device_id": "OLT-A", "type": "OLT"}, {"device_id": "OLT-B", "type": "OLT"}],
        "ports": [{"port_id": "OLT-A:1", "device_id": "OLT-A", "direction": "out"}, {"port_id": "OLT-B:1", "device_id": "OLT-B", "direction": "in"}],
        "links": [{"link_id": "A-B", "endpoint_a": "OLT-A:1", "endpoint_b": "OLT-B:1", "length_km": 10.5}],
    }
    with csv_path.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(topology, ensure_ascii=False)},
        )
    body = response.json()
    dossier_id = body["dossier_id"]

    # Inject ground truth into the archived dossier.
    dossier = store.get_session(dossier_id)
    dossier["feedback_layer"]["ground_truth"] = {"root_cause": "link:A-B"}
    store.upsert_session(dossier_id, dossier.get("status", "success"), dossier)
    return dossier_id


@pytest.fixture
def degraded_dosser_id(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    monkeypatch.setattr("optirc_lite.config.settings.lancedb_path", tmp_path / "lancedb")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    csv_path = tmp_path / "alarms.csv"
    csv_path.write_text(
        "告警源,名称,定位信息,级别,时间\n"
        "NE-OTN-01,MUT_LOS,机房A,critical,2026-08-04T10:00:00Z\n"
        "NE-OTN-02,MUT_LOS,机房B,critical,2026-08-04T10:00:01Z\n",
        encoding="utf-8",
    )
    topology = {
        "devices": [{"device_id": "NE-OTN-01", "type": "OTN"}, {"device_id": "NE-OTN-02", "type": "OTN"}],
        "ports": [],
        "links": [],
    }
    with csv_path.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(topology, ensure_ascii=False)},
        )
    body = response.json()
    dossier_id = body["dossier_id"]
    dossier = store.get_session(dossier_id)
    dossier["feedback_layer"]["ground_truth"] = {"root_cause": "dev:NE-OTN-01"}
    store.upsert_session(dossier_id, dossier.get("status", "degraded"), dossier)
    return dossier_id


def test_evaluate_returns_report_url_and_is_retrievable(success_dossier_id):
    response = client.post("/v1/evaluate", json={"dossier_ids": [success_dossier_id]})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "evaluation_id" in body
    assert body["report_url"].startswith("/v1/evaluate/")

    report_response = client.get(body["report_url"])
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["metrics"]["top1_acc"] == 1.0
    assert report["metrics"]["top3_recall"] == 1.0
    assert report["error_attribution"] == {}


def test_evaluate_degraded_case_attributes_error(degraded_dosser_id):
    response = client.post("/v1/evaluate", json={"dossier_ids": [degraded_dosser_id]})
    report = response.json()
    report_response = client.get(report["report_url"])
    full_report = report_response.json()

    case = full_report["cases"][0]
    assert case["degraded"] is True
    assert any(item["lever"] in {"critic", "judge"} for item in case["error_attribution"])


def test_evaluate_empty_dossier_ids_returns_400():
    response = client.post("/v1/evaluate", json={"dossier_ids": []})
    assert response.status_code == 400


def test_evaluate_not_found_returns_404():
    response = client.get("/v1/evaluate/EVAL-DOES-NOT-EXIST")
    assert response.status_code == 404
