"""Diagnosis-sample input preparation and topology preflight."""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable

from optirc_lite.config import settings


@dataclass(frozen=True)
class PreflightRecord:
    preflight_id: str
    alarm_path: str
    filename: str
    fact_table: Dict[str, Any]
    topology: Dict[str, Any]
    status: str
    issues: list[Dict[str, Any]]
    consumed_by: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preflight_id": self.preflight_id,
            "alarm_path": self.alarm_path,
            "filename": self.filename,
            "fact_table": self.fact_table,
            "topology": self.topology,
            "status": self.status,
            "issues": self.issues,
            "consumed_by": self.consumed_by,
        }


class PreflightRepository:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root
        self._claim_lock = Lock()

    @property
    def path(self) -> Path:
        return self.root or settings.upload_dir / "preflights"

    def save(self, record: PreflightRecord) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / f"{record.preflight_id}.json").write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, preflight_id: str) -> PreflightRecord | None:
        path = self.path / f"{preflight_id}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PreflightRecord(**payload)

    def claim(self, preflight_id: str, session_id: str) -> PreflightRecord | None:
        """Atomically consume a ready preflight once within this API process."""
        with self._claim_lock:
            record = self.get(preflight_id)
            if record is None or record.status != "ready" or record.consumed_by:
                return None
            claimed = replace(record, consumed_by=session_id)
            self.save(claimed)
            return claimed


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def sample_summary(fact_table: Dict[str, Any]) -> Dict[str, Any]:
    alarms = fact_table.get("alarms", [])
    timestamps = sorted(_unique(str(alarm.get("timestamp", "")) for alarm in alarms))
    return {
        "alarm_count": len(alarms),
        "severity_counts": dict(Counter(str(alarm.get("severity", "unknown")) for alarm in alarms)),
        "device_count": len(_unique(str(alarm.get("device_id", "")) for alarm in alarms)),
        "alarm_types": _unique(str(alarm.get("type", "")) for alarm in alarms),
        "time_window": {
            "start": timestamps[0] if timestamps else None,
            "end": timestamps[-1] if timestamps else None,
        },
    }


def _normalize_provided_topology(topology: Dict[str, Any]) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    devices = topology.get("devices")
    ports = topology.get("ports")
    links = topology.get("links")
    if not isinstance(devices, list) or not isinstance(ports, list) or not isinstance(links, list):
        return {}, [
            {
                "code": "TOPOLOGY_INVALID",
                "message": "拓扑 JSON 必须包含 devices、ports 和 links 数组。",
                "required_fields": ["devices", "ports", "links"],
            }
        ]

    port_ids = {port.get("port_id") for port in ports if isinstance(port, dict)}
    invalid_links = [
        link.get("link_id", "unknown")
        for link in links
        if not isinstance(link, dict)
        or link.get("endpoint_a") not in port_ids
        or link.get("endpoint_b") not in port_ids
    ]
    if invalid_links:
        return {}, [
            {
                "code": "TOPOLOGY_ENDPOINT_INVALID",
                "message": "部分链路端点未引用已声明的端口。",
                "objects": invalid_links,
                "required_fields": ["ports[].port_id", "links[].endpoint_a", "links[].endpoint_b"],
            }
        ]

    return {
        "source": "provided",
        "confidence": 1.0,
        "devices": devices,
        "ports": ports,
        "links": [
            {**link, "confidence": 1.0, "inferred": False}
            for link in links
        ],
        "inference_explanations": [],
    }, []


def _port_parts(port_id: str) -> tuple[str, str] | None:
    if ":" not in port_id:
        return None
    device_id, link_hint = port_id.split(":", 1)
    if not device_id or not link_hint:
        return None
    return device_id, link_hint


def infer_topology(fact_table: Dict[str, Any]) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    alarms = fact_table.get("alarms", [])
    devices = _unique(str(alarm.get("device_id", "")).strip() for alarm in alarms)
    port_ids = _unique(str(alarm.get("port_id", "")).strip() for alarm in alarms)

    if not devices:
        return {}, [
            {
                "code": "DEVICE_ID_MISSING",
                "message": "告警中缺少可识别的设备标识。",
                "required_fields": ["device_id"],
            }
        ]

    if len(devices) == 1:
        ports = [
            {"port_id": port_id, "device_id": devices[0], "direction": None}
            for port_id in port_ids
        ]
        return {
            "source": "inferred",
            "confidence": 0.75,
            "devices": [{"device_id": devices[0], "type": "unknown"}],
            "ports": ports,
            "links": [],
            "inference_explanations": ["全部相关告警明确收敛于同一设备。"],
        }, []

    if not port_ids:
        return {}, [
            {
                "code": "TOPOLOGY_AMBIGUOUS",
                "message": "多设备告警缺少端口信息，无法唯一还原连接关系，请补充拓扑 JSON。",
                "objects": devices,
                "required_fields": ["port_id", "topology.json"],
            }
        ]

    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    invalid_ports: list[str] = []
    for port_id in port_ids:
        parts = _port_parts(port_id)
        if parts is None:
            invalid_ports.append(port_id)
            continue
        device_id, link_hint = parts
        if device_id not in devices:
            invalid_ports.append(port_id)
            continue
        grouped[link_hint].append((device_id, port_id))

    ambiguous = invalid_ports or any(
        len(endpoints) != 2 or len({device_id for device_id, _ in endpoints}) != 2
        for endpoints in grouped.values()
    )
    connected_devices = {device_id for endpoints in grouped.values() for device_id, _ in endpoints}
    if ambiguous or connected_devices != set(devices):
        return {}, [
            {
                "code": "TOPOLOGY_AMBIGUOUS",
                "message": "告警端口无法形成唯一的两端链路关系，请补充拓扑 JSON。",
                "objects": invalid_ports or devices,
                "required_fields": ["topology.json"],
            }
        ]

    ports: list[Dict[str, Any]] = []
    links: list[Dict[str, Any]] = []
    explanations: list[str] = []
    for link_hint in sorted(grouped):
        endpoints = sorted(grouped[link_hint])
        endpoint_a = endpoints[0][1]
        endpoint_b = endpoints[1][1]
        ports.extend(
            [
                {"port_id": endpoint_a, "device_id": endpoints[0][0], "direction": "out"},
                {"port_id": endpoint_b, "device_id": endpoints[1][0], "direction": "in"},
            ]
        )
        explanation = f"告警端口共同指向链路 {link_hint}"
        explanations.append(explanation)
        links.append(
            {
                "link_id": link_hint,
                "endpoint_a": endpoint_a,
                "endpoint_b": endpoint_b,
                "confidence": 0.8,
                "inferred": True,
                "inference_explanation": explanation,
            }
        )

    return {
        "source": "inferred",
        "confidence": 0.8,
        "devices": [{"device_id": device_id, "type": "unknown"} for device_id in devices],
        "ports": ports,
        "links": links,
        "inference_explanations": explanations,
    }, []


def prepare_topology(
    fact_table: Dict[str, Any], topology: Dict[str, Any] | None
) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    if topology is not None:
        return _normalize_provided_topology(topology)
    return infer_topology(fact_table)


preflight_repository = PreflightRepository()
