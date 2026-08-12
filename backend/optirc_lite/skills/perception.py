from pathlib import Path
from typing import Any, Dict, List

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import DefaultSkillInput, PerceptionSkillOutput
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class AlarmPerceptionSkill:
    name = "perception.alarm_csv"
    description = "Parse alarm CSV and normalize key RCA fields."
    required_tools = ["csv.parse"]
    input_schema = DefaultSkillInput
    output_schema = PerceptionSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("raw_input", "").lower().endswith(".csv") else 0.2

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        parsed = await tools.call("csv.parse", path=state["raw_input"])
        rows: List[Dict[str, Any]] = parsed["rows"]
        first = rows[0] if rows else {}

        alarm_col = self._pick(first, ["alarm_type", "alarm_name", "名称", "告警名称", "name"], fallback=True)
        device_col = self._pick(first, ["device_id", "device", "source", "告警源", "网元", "设备", "ne_id"], fallback=True)
        port_col = self._pick(first, ["port_id", "port", "端口", "port_name"], fallback=False)
        location_col = self._pick(first, ["location", "定位信息", "description", "desc"], fallback=True)
        time_col = self._pick(first, ["timestamp", "time", "时间", "告警时间", "最近发生时间"], fallback=True)
        severity_col = self._pick(first, ["severity", "级别", "告警级别", "level"], fallback=True)

        alarms = []
        alarm_types = []
        devices = []
        for idx, row in enumerate(rows):
            alarm = str(row.get(alarm_col, "")).strip() if alarm_col else ""
            device = str(row.get(device_col, "")).strip() if device_col else ""
            if alarm and alarm not in alarm_types:
                alarm_types.append(alarm)
            if device and device not in devices:
                devices.append(device)

            port_id = str(row.get(port_col, "")).strip() if port_col else ""

            alarms.append({
                "alarm_id": f"ALM-{idx:04d}",
                "type": alarm,
                "severity": str(row.get(severity_col, "")).strip() if severity_col else "",
                "timestamp": str(row.get(time_col, "")).strip() if time_col else "",
                "device_id": device,
                "port_id": port_id,
                "raw_text": str(row),
            })

        result = {
            "input_name": Path(state["raw_input"]).name,
            "alarm_count": len(rows),
            "headers": parsed["headers"],
            "first_row": first,
            "alarms": alarms,
            "alarm_types": alarm_types[:10],
            "devices": devices[:20],
            "primary_alarm": alarm_types[0] if alarm_types else "unknown",
            "primary_device": devices[0] if devices else "",
            "description": str(first.get(location_col, "")) if location_col else "",
        }
        return {
            "result": result,
            "confidence": 0.9 if rows else 0.2,
            "evidence": [f"解析到 {len(rows)} 条告警", f"识别设备 {len(devices)} 个"],
            "observations": [{"type": "csv_summary", "value": result}],
            "next_suggestions": ["topology.topology_builder"],
        }

    @staticmethod
    def _pick(row: Dict[str, Any], candidates: List[str], fallback: bool = True) -> str | None:
        lowered = {key.lower(): key for key in row.keys()}
        for candidate in candidates:
            if candidate in row:
                return candidate
            if candidate.lower() in lowered:
                return lowered[candidate.lower()]
        if fallback:
            return next(iter(row.keys()), None) if row else None
        return None
