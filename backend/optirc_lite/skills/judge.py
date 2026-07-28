"""Propagation Judge — generates candidate root-cause propagation chains."""

from typing import Any, Dict, List, Set

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import DefaultSkillInput, JudgeSkillOutput
from optirc_lite.storage.evidence_graph import (
    EvidenceGraph,
    NodeType,
)
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class PropagationJudgeSkill:
    name = "judge.root_cause_judge"
    description = "Generate candidate root-cause propagation chains from the evidence graph."
    required_tools = []
    input_schema = DefaultSkillInput
    output_schema = JudgeSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("perception") and state.get("evidence_graph") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        fact_table: Dict[str, Any] = state.get("perception", {})
        graph = EvidenceGraph()

        alarms = {n.id: n for n in graph.get_nodes(NodeType.ALARM)}
        links = graph.get_nodes(NodeType.LINK)
        devices = graph.get_nodes(NodeType.DEVICE)

        candidates: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        # Link candidates: a broken link often produces LOS/MUT_LOS on both endpoints.
        ports = graph.get_nodes(NodeType.PORT)
        port_by_property = {p.properties.get("port_id", p.id): p.id for p in ports}

        for link in links:
            link_id = link.properties.get("link_id", link.id)
            key = f"link:{link_id}"
            chain_alarms: List[str] = []

            for endpoint in (link.properties.get("endpoint_a"), link.properties.get("endpoint_b")):
                if not endpoint:
                    continue
                port_node_id = port_by_property.get(endpoint, f"port:{endpoint}")
                for alarm in graph.get_alarms_for_node(port_node_id):
                    alarm_type = alarm.properties.get("alarm_type", "alarm")
                    chain_alarms.append(f"{alarm_type} @ {endpoint}")

            if chain_alarms:
                seen.add(key)
                candidates.append(
                    {
                        "root_cause": key,
                        "confidence": 0.8,
                        "score_vector": [],
                        "evidence_chain": [
                            f"candidate root cause: {key}",
                            f"endpoints: {link.properties.get('endpoint_a') or '-'} / {link.properties.get('endpoint_b') or '-'}",
                            *chain_alarms,
                        ],
                    }
                )

        # Device candidates for any alarm-bearing device not already covered by a link.
        for device in devices:
            _, device_id = graph.parse_node_id(device.id)
            alarm_ids = {a.id for a in graph.get_alarms_for_node(device.id)}
            if not alarm_ids:
                continue
            key = f"dev:{device_id}"
            if key in seen:
                continue
            seen.add(key)
            chain_alarms = [
                f"{alarms[a].properties.get('alarm_type', 'alarm')} @ {device_id}"
                for a in alarm_ids
                if a in alarms
            ]
            candidates.append(
                {
                    "root_cause": key,
                    "confidence": 0.6,
                    "score_vector": [],
                    "evidence_chain": [
                        f"candidate root cause: {key}",
                        *chain_alarms,
                    ],
                }
            )

        # Fallback: if the graph is empty, return a single degraded candidate.
        if not candidates and fact_table.get("alarm_count", 0) == 0:
            candidates.append(
                {
                    "root_cause": "unknown",
                    "confidence": 0.0,
                    "score_vector": [],
                    "evidence_chain": ["no alarms or topology available"],
                }
            )

        return {
            "result": {"candidates": candidates},
            "confidence": 0.8 if candidates else 0.2,
            "evidence": [f"生成 {len(candidates)} 条候选传播链"],
            "observations": [{"type": "judge_candidates", "value": {"count": len(candidates)}}],
            "next_suggestions": ["rank.candidate_ranker"],
        }
