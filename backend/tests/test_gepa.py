"""Tests for GEPA Strategy Optimizer Pareto frontier and candidate quality."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from optirc_lite.api.main import app
from optirc_lite.storage.evidence_graph import EvidenceGraph
from optirc_lite.storage.sqlite_store import store


client = TestClient(app)


@pytest.fixture
def evaluation_id(tmp_path, monkeypatch):
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
        "ports": [
            {"port_id": "OLT-A:1", "device_id": "OLT-A", "direction": "out"},
            {"port_id": "OLT-B:1", "device_id": "OLT-B", "direction": "in"},
        ],
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

    dossier = store.get_session(dossier_id)
    dossier["feedback_layer"]["ground_truth"] = {"root_cause": "link:A-B"}
    store.upsert_session(dossier_id, dossier.get("status", "success"), dossier)

    eval_response = client.post("/v1/evaluate", json={"dossier_ids": [dossier_id]})
    return eval_response.json()["evaluation_id"]


def test_gepa_returns_report_url_and_is_retrievable(evaluation_id):
    response = client.post(
        "/v1/gepa",
        json={"evaluation_id": evaluation_id, "population_size": 3, "max_generations": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "optimization_id" in body
    assert body["report_url"].startswith("/v1/gepa/")

    report_response = client.get(body["report_url"])
    assert report_response.status_code == 200
    report = report_response.json()
    assert len(report["pareto_frontier"]) > 0
    assert report["recommended_candidate"] is not None
    assert report["baseline"] is not None


def test_gepa_recommended_candidate_has_valid_weights(evaluation_id):
    response = client.post(
        "/v1/gepa",
        json={"evaluation_id": evaluation_id, "population_size": 3, "max_generations": 2},
    )
    report = client.get(response.json()["report_url"]).json()
    weights = report["recommended_candidate"]["chromosome"]["weights"]
    assert set(weights.keys()) == {
        "upstream",
        "time_lead",
        "coverage",
        "priority",
        "case_sim",
        "conflict_penalty",
    }
    assert all(0.0 <= v <= 1.0 for v in weights.values())
    assert abs(sum(weights.values()) - 1.0) < 1e-3


def test_gepa_recommended_candidate_improves_baseline(evaluation_id):
    response = client.post(
        "/v1/gepa",
        json={"evaluation_id": evaluation_id, "population_size": 3, "max_generations": 2},
    )
    report = client.get(response.json()["report_url"]).json()
    baseline = report["baseline"]["fitness"]
    recommended = report["recommended_candidate"]["fitness"]

    improvements = sum(1 for r, b in zip(recommended, baseline) if r > b)
    regressions = sum(1 for r, b in zip(recommended, baseline) if r < b)
    assert improvements >= 1
    assert regressions == 0


def test_gepa_missing_evaluation_returns_404():
    response = client.post(
        "/v1/gepa",
        json={"evaluation_id": "EVAL-DOES-NOT-EXIST", "population_size": 3, "max_generations": 2},
    )
    assert response.status_code == 404


def test_gepa_not_found_returns_404():
    response = client.get("/v1/gepa/GEPA-DOES-NOT-EXIST")
    assert response.status_code == 404
