"""Propagation Judge — generates candidate root-cause propagation chains."""

from typing import Any, Dict, List, Set

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import DefaultSkillInput, JudgeSkillOutput
from optirc_lite.storage.evidence_graph import (
    EdgeType,
    EvidenceGraph,
    EvidenceNode,
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
        ports = graph.get_nodes(NodeType.PORT)

        # Build quick lookup indexes
        belongs = graph.get_edges(EdgeType.BELONGS_TO)
        topo = graph.get_edges(EdgeType.TOPOLOGY)

        alarm_to_target: Dict[str, str] = {e.source: e.target for e in belongs}
        target_to_alarms: Dict[str, List[str]] = {}
        for e in belongs:
            target_to_alarms.setdefault(e.target, []).append(e.source)

        topo_source_to_target: Dict[str, str] = {e.source: e.target for e in topo}
        topo_target_to_source: Dict[str, str] = {e.target: e.source for e in topo}

        candidates: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        # Link candidates: a broken link often produces LOS/MUT_LOS on both endpoints.
        for link in links:
            link_id = link.properties.get("link_id", link.id)
            endpoint_a = link.properties.get("endpoint_a")
            endpoint_b = link.properties.get("endpoint_b")
            chain_alarms: List[str] = []

            for endpoint in (endpoint_a, endpoint_b):
                if not endpoint:
                    continue
                # endpoint is a port id; resolve to device if needed
                port_node = next((p for p in ports if p.properties.get("port_id") == endpoint), None)
                device_id = port_node.properties.get("device_id") if port_node else None
                alarm_ids = target_to_alarms.get(f"port:{endpoint}", [])
                if device_id:
                    alarm_ids.extend(target_to_alarms.get(f"dev:{device_id}", []))
                for alarm_id in set(alarm_ids):
                    alarm = alarms.get(alarm_id)
                    if alarm:
                        chain_alarms.append(
                            f"{alarm.properties.get('alarm_type', 'alarm')} @ {device_id or endpoint}"
                        )

            if chain_alarms:
                key = f"link:{link_id}"
                seen.add(key)
                candidates.append(
                    {
                        "root_cause": key,
                        "confidence": 0.8,
                        "score_vector": [],
                        "evidence_chain": [
                            f"candidate root cause: {key}",
                            f"endpoints: {endpoint_a or '-'} / {endpoint_b or '-'}",
                            *chain_alarms,
                        ],
                    }
                )

        # Device candidates for any alarm-bearing device not already covered by a link.
        for device in devices:
            device_id = device.properties.get("device_id", device.id)
            alarm_ids = target_to_alarms.get(f"dev:{device_id}", [])
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
