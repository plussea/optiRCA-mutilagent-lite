"""Public API tests for diagnosis-sample topology preflight."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from optirc_lite.api.main import app


client = TestClient(app)


def _write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text(
        "alarm_type,severity,device_id,port_id,timestamp\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_preflight_accepts_authoritative_topology(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.upload_dir", tmp_path / "uploads")
    alarms = _write_csv(
        tmp_path / "alarms.csv",
        [
            "OTS_LOS,critical,N1,N1:N1-N2,2026-08-11T14:58:00Z",
            "OSC_LOS,critical,N2,N2:N1-N2,2026-08-11T14:58:01Z",
        ],
    )
    topology = {
        "devices": [{"device_id": "N1"}, {"device_id": "N2"}],
        "ports": [
            {"port_id": "N1:N1-N2", "device_id": "N1", "direction": "out"},
            {"port_id": "N2:N1-N2", "device_id": "N2", "direction": "in"},
        ],
        "links": [
            {"link_id": "N1-N2", "endpoint_a": "N1:N1-N2", "endpoint_b": "N2:N1-N2"}
        ],
    }

    with alarms.open("rb") as alarms_file:
        response = client.post(
            "/api/v1/preflight",
            files={"alarms": ("alarms.csv", alarms_file, "text/csv")},
            data={"topology": json.dumps(topology)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["preflight_id"].startswith("PF-")
    assert body["sample_summary"]["alarm_count"] == 2
    assert body["topology"]["source"] == "provided"
    assert body["topology"]["confidence"] == 1.0


def test_preflight_infers_unique_link_from_alarm_ports(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.upload_dir", tmp_path / "uploads")
    alarms = _write_csv(
        tmp_path / "alarms.csv",
        [
            "OTS_LOS,critical,N1,N1:N1-N2,2026-08-11T14:58:00Z",
            "OSC_LOS,critical,N2,N2:N1-N2,2026-08-11T14:58:01Z",
        ],
    )

    with alarms.open("rb") as alarms_file:
        response = client.post(
            "/api/v1/preflight",
            files={"alarms": ("alarms.csv", alarms_file, "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["topology"]["source"] == "inferred"
    assert body["topology"]["confidence"] < 1.0
    assert body["topology"]["links"] == [
        {
            "link_id": "N1-N2",
            "endpoint_a": "N1:N1-N2",
            "endpoint_b": "N2:N1-N2",
            "confidence": 0.8,
            "inferred": True,
            "inference_explanation": "告警端口共同指向链路 N1-N2",
        }
    ]


def test_preflight_blocks_ambiguous_multi_device_csv(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.upload_dir", tmp_path / "uploads")
    alarms = _write_csv(
        tmp_path / "alarms.csv",
        [
            "MUT_LOS,critical,N1,,2026-08-11T14:58:00Z",
            "MUT_LOS,critical,N2,,2026-08-11T14:58:01Z",
        ],
    )

    with alarms.open("rb") as alarms_file:
        response = client.post(
            "/api/v1/preflight",
            files={"alarms": ("alarms.csv", alarms_file, "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "input_not_ready"
    assert body["preflight_id"].startswith("PF-")
    assert body["issues"][0]["code"] == "TOPOLOGY_AMBIGUOUS"
    assert body["topology"]["links"] == []
