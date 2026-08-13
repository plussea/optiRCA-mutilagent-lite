"""Public-contract tests for the asynchronous diagnosis workbench API."""

import json
import asyncio
import time
from pathlib import Path

from fastapi.testclient import TestClient

from optirc_lite.api.main import app
from optirc_lite.api import main


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _create_demo_preflight(client: TestClient) -> str:
    with (PROJECT_ROOT / "demo" / "01" / "alarm.csv").open("rb") as alarms:
        response = client.post(
            "/api/v1/preflight",
            files={"alarms": ("alarm.csv", alarms, "text/csv")},
            data={
                "topology": (PROJECT_ROOT / "demo" / "01" / "topology.json").read_text(
                    encoding="utf-8"
                )
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    return response.json()["preflight_id"]


def _wait_for_terminal(client: TestClient, session_id: str) -> dict:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/diagnoses/{session_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"success", "degraded", "cancelled"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("diagnosis did not reach a terminal state")


def test_async_diagnosis_persists_real_events_and_supports_recovery():
    with TestClient(app) as client:
        preflight_id = _create_demo_preflight(client)
        created = client.post(
            "/api/v1/diagnoses",
            json={"preflight_id": preflight_id, "max_fallback_rounds": 2},
        )

        assert created.status_code == 202
        session_id = created.json()["session_id"]
        assert created.json()["status"] == "running"
        assert created.json()["events_url"].endswith(f"/{session_id}/events")

        recovered = _wait_for_terminal(client, session_id)
        assert recovered["status"] == "success"
        assert recovered["result"]["root_cause"]["root_cause"] == "link:N1-N2"

        event_response = client.get(f"/api/v1/diagnoses/{session_id}/events")
        assert event_response.status_code == 200
        event_blocks = [block for block in event_response.text.split("\n\n") if block.strip()]
        ids = [
            int(line.removeprefix("id: "))
            for block in event_blocks
            for line in block.splitlines()
            if line.startswith("id: ")
        ]
        payloads = [
            json.loads(line.removeprefix("data: "))
            for block in event_blocks
            for line in block.splitlines()
            if line.startswith("data: ")
        ]
        event_types = [payload["type"] for payload in payloads]

        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))
        assert event_types[0] == "diagnosis.started"
        assert "stage.started" in event_types
        assert "stage.completed" in event_types
        assert "topology.updated" in event_types
        assert "candidates.updated" in event_types
        assert "critic.checked" in event_types
        assert event_types[-1] == "diagnosis.completed"
        completed_stages = [
            payload for payload in payloads if payload["type"] == "stage.completed"
        ]
        assert all(payload["elapsed_ms"] >= 0 for payload in completed_stages)


def test_diagnosis_creation_rejects_preflight_that_was_already_consumed():
    with TestClient(app) as client:
        preflight_id = _create_demo_preflight(client)
        first = client.post("/api/v1/diagnoses", json={"preflight_id": preflight_id})
        second = client.post("/api/v1/diagnoses", json={"preflight_id": preflight_id})

        assert first.status_code == 202
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "PREFLIGHT_ALREADY_CONSUMED"
        _wait_for_terminal(client, first.json()["session_id"])


def test_not_ready_preflight_cannot_create_a_diagnosis(tmp_path):
    csv_path = tmp_path / "ambiguous.csv"
    csv_path.write_text(
        "device_id,alarm_type,severity,timestamp\n"
        "N1,LOS,critical,2026-08-03T10:00:00Z\n"
        "N2,LOS,critical,2026-08-03T10:00:01Z\n",
        encoding="utf-8",
    )

    with TestClient(app) as client, csv_path.open("rb") as alarms:
        preflight = client.post(
            "/api/v1/preflight",
            files={"alarms": ("ambiguous.csv", alarms, "text/csv")},
        )
        created = client.post(
            "/api/v1/diagnoses",
            json={"preflight_id": preflight.json()["preflight_id"]},
        )

    assert preflight.json()["status"] == "input_not_ready"
    assert created.status_code == 409
    assert created.json()["detail"]["code"] == "PREFLIGHT_NOT_READY"


def test_review_confirmed_records_current_prediction_as_ground_truth():
    with TestClient(app) as client:
        preflight_id = _create_demo_preflight(client)
        created = client.post("/api/v1/diagnoses", json={"preflight_id": preflight_id})
        result = _wait_for_terminal(client, created.json()["session_id"])

        reviewed = client.post(
            f"/api/v1/diagnoses/{result['session_id']}/review",
            json={"decision": "confirmed", "notes": "现场复核确认"},
        )
        dossier = client.get(f"/v1/dossier/{result['dossier_id']}")

    assert reviewed.status_code == 200
    assert reviewed.json()["review"]["status"] == "confirmed"
    assert reviewed.json()["review"]["ground_truth"] == {"root_cause": "link:N1-N2"}
    assert dossier.json()["output_layer"]["root_cause"]["root_cause"] == "link:N1-N2"
    assert dossier.json()["feedback_layer"]["human_decision"] == "confirmed"
    assert dossier.json()["feedback_layer"]["ground_truth"] == {"root_cause": "link:N1-N2"}


def test_corrected_review_requires_a_root_from_the_business_topology():
    with TestClient(app) as client:
        preflight_id = _create_demo_preflight(client)
        created = client.post("/api/v1/diagnoses", json={"preflight_id": preflight_id})
        result = _wait_for_terminal(client, created.json()["session_id"])
        endpoint = f"/api/v1/diagnoses/{result['session_id']}/review"

        missing = client.post(endpoint, json={"decision": "corrected"})
        invalid = client.post(
            endpoint,
            json={"decision": "corrected", "ground_truth": {"root_cause": "link:NOT-THERE"}},
        )
        valid = client.post(
            endpoint,
            json={"decision": "corrected", "ground_truth": {"root_cause": "dev:N1"}},
        )

    assert missing.status_code == 422
    assert invalid.status_code == 422
    assert valid.status_code == 200
    assert valid.json()["review"]["ground_truth"] == {"root_cause": "dev:N1"}


def test_sse_last_event_id_replays_only_later_persisted_events():
    with TestClient(app) as client:
        preflight_id = _create_demo_preflight(client)
        created = client.post("/api/v1/diagnoses", json={"preflight_id": preflight_id})
        session_id = created.json()["session_id"]
        _wait_for_terminal(client, session_id)

        all_events = client.get(f"/api/v1/diagnoses/{session_id}/events")
        ids = [
            int(line.removeprefix("id: "))
            for line in all_events.text.splitlines()
            if line.startswith("id: ")
        ]
        resumed = client.get(
            f"/api/v1/diagnoses/{session_id}/events",
            headers={"Last-Event-ID": str(ids[-2])},
        )

    resumed_ids = [
        int(line.removeprefix("id: "))
        for line in resumed.text.splitlines()
        if line.startswith("id: ")
    ]
    assert resumed_ids == [ids[-1]]


def test_cancelled_diagnosis_has_no_dossier(monkeypatch):
    class SlowWorkflow:
        async def ainvoke(self, _state):
            await asyncio.Event().wait()

    monkeypatch.setattr(main, "build_workflow", lambda: SlowWorkflow())
    with TestClient(app) as client:
        preflight_id = _create_demo_preflight(client)
        created = client.post("/api/v1/diagnoses", json={"preflight_id": preflight_id})
        session_id = created.json()["session_id"]
        cancelled = client.post(f"/api/v1/diagnoses/{session_id}/cancel")
        time.sleep(0.05)
        recovered = client.get(f"/api/v1/diagnoses/{session_id}")

    assert cancelled.status_code == 202
    assert recovered.json()["status"] == "cancelled"
    assert recovered.json()["dossier_id"] is None
