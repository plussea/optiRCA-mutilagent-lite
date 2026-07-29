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


@pytest.fixture
def demo8_alarm_csv():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "alarms.csv"
        path.write_text(
            "告警源,名称,定位信息,级别,时间\n"
            "NE-B,MUT_LOS,核心机房-ODF-B,critical,2026-07-27T10:00:00Z\n"
            "NE-C,MUT_LOS,核心机房-ODF-C,critical,2026-07-27T10:00:01Z\n",
            encoding="utf-8",
        )
        yield path


@pytest.fixture
def demo8_topology_json():
    devices = [f"NE-{name}" for name in "ABCDEFGH"]
    topology = {"devices": [], "ports": [], "links": []}
    for device_id in devices:
        topology["devices"].append({"device_id": device_id, "type": "OTN"})

    # Chain topology: A-B-C-D-E-F-G-H with B-C as the failing fiber.
    links = [
        ("NE-A", "NE-B", "A-B"),
        ("NE-B", "NE-C", "B-C"),
        ("NE-C", "NE-D", "C-D"),
        ("NE-D", "NE-E", "D-E"),
        ("NE-E", "NE-F", "E-F"),
        ("NE-F", "NE-G", "F-G"),
        ("NE-G", "NE-H", "G-H"),
    ]
    for endpoint_a, endpoint_b, link_id in links:
        port_a = f"{endpoint_a}:{link_id}"
        port_b = f"{endpoint_b}:{link_id}"
        topology["ports"].append({"port_id": port_a, "device_id": endpoint_a, "direction": "out"})
        topology["ports"].append({"port_id": port_b, "device_id": endpoint_b, "direction": "in"})
        topology["links"].append(
            {"link_id": link_id, "endpoint_a": port_a, "endpoint_b": port_b, "length_km": 10.0}
        )
    return topology


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
    assert body["degradation_reason"] == "agent_failure"


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
    assert body["degradation_reason"] == "agent_failure"


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


def test_diagnose_8node_fiber_cut_returns_link_root_cause(
    demo8_alarm_csv, demo8_topology_json, tmp_path, monkeypatch
):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    with demo8_alarm_csv.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(demo8_topology_json, ensure_ascii=False)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["requires_human_review"] is False
    assert "dossier_id" in body
    assert "session_id" in body
    root_cause = body.get("root_cause") or {}
    assert root_cause.get("root_cause") == "link:B-C"
    assert "evidence_chain" in body
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["critic_verdict"] == "pass"

    # The dossier should be retrievable from the store.
    from optirc_lite.storage.sqlite_store import store

    dossier = store.get_dossier(body["dossier_id"])
    assert dossier is not None
    assert dossier["session_id"] == body["session_id"]
    assert dossier["status"] == "success"
    assert dossier["requires_human_review"] in (0, 1)
