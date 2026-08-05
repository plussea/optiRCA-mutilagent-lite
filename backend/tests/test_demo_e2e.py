"""End-to-end demo test using demo/ fault sample."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from optirc_lite.api.main import app
from optirc_lite.storage.evidence_graph import EvidenceGraph


client = TestClient(app)


def _load_demo_assets():
    demo_dir = Path(__file__).parent.parent.parent / "demo"
    alarms = (demo_dir / "8node_fiber_cut_alarms.csv").read_text(encoding="utf-8")
    topology = json.loads((demo_dir / "8node_fiber_cut_topology.json").read_text(encoding="utf-8"))
    return alarms, topology


def test_demo_fiber_cut_returns_link_bc(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    monkeypatch.setattr("optirc_lite.config.settings.lancedb_path", tmp_path / "lancedb")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    alarms_text, topology = _load_demo_assets()
    csv_path = tmp_path / "alarms.csv"
    csv_path.write_text(alarms_text, encoding="utf-8")

    with csv_path.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(topology, ensure_ascii=False)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["requires_human_review"] is False
    root_cause = body.get("root_cause") or {}
    assert root_cause.get("root_cause") == "link:B-C"
    assert body["critic_verdict"] == "pass"
    assert "dossier_id" in body

    evidence_graph = body["evidence_graph"]
    alarm_nodes = [n for n in evidence_graph.get("nodes", []) if n.get("type") == "Alarm"]
    assert len(alarm_nodes) == 2


def test_demo_fiber_cut_dossier_retrievable(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    monkeypatch.setattr("optirc_lite.config.settings.lancedb_path", tmp_path / "lancedb")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    alarms_text, topology = _load_demo_assets()
    csv_path = tmp_path / "alarms.csv"
    csv_path.write_text(alarms_text, encoding="utf-8")

    with csv_path.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(topology, ensure_ascii=False)},
        )

    body = response.json()
    dossier_id = body["dossier_id"]
    response = client.get(f"/v1/dossier/{dossier_id}")
    assert response.status_code == 200
    dossier = response.json()
    assert dossier["dossier_id"] == dossier_id
    assert dossier["output_layer"]["root_cause"]["root_cause"] == "link:B-C"
    assert dossier["metadata"]["critic_verdict"] == "pass"
    assert dossier["metadata"].get("degradation_reason") is None
