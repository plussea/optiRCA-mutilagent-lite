"""Root Cause Ranker — scores and sorts candidate propagation chains."""

from typing import Any, Dict, List

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import DefaultSkillInput, RankSkillOutput
from optirc_lite.storage.evidence_graph import (
    EdgeType,
    EvidenceGraph,
    NodeType,
)
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class RootCauseRankerSkill:
    name = "rank.candidate_ranker"
    description = "Score candidate root causes with a six-dimensional vector and rank them."
    required_tools = []
    input_schema = DefaultSkillInput
    output_schema = RankSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("judge") and state.get("evidence_graph") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        judge_result: Dict[str, Any] = state.get("judge", {})
        candidates: List[Dict[str, Any]] = list(judge_result.get("candidates", []))
        fact_table: Dict[str, Any] = state.get("perception", {})
        graph = EvidenceGraph()

        alarms = {n.id: n for n in graph.get_nodes(NodeType.ALARM)}
        total_alarms = max(len(alarms), fact_table.get("alarm_count", len(alarms)))
        alarm_types = [a.properties.get("alarm_type", "").lower() for a in alarms.values()]
        has_fiber_cut = any("los" in t for t in alarm_types)

        scored = []
        for candidate in candidates:
            score = self._score(candidate, alarms, total_alarms, has_fiber_cut, graph)
            candidate["score_vector"] = score
            candidate["confidence"] = round(sum(score) / max(len(score), 1), 3)
            scored.append(candidate)

        scored.sort(key=lambda c: c["confidence"], reverse=True)

        return {
            "result": {"candidates": scored},
            "confidence": 0.9 if scored else 0.2,
            "evidence": [f"排序后返回 {len(scored)} 个候选根因"],
            "observations": [{"type": "rank_candidates", "value": {"count": len(scored)}}],
            "next_suggestions": ["critic.diagnosis_critic"],
        }

    def _score(
        self,
        candidate: Dict[str, Any],
        alarms: Dict[str, Any],
        total_alarms: int,
        has_fiber_cut: bool,
        graph: EvidenceGraph,
    ) -> List[float]:
        root_cause = candidate.get("root_cause", "")
        evidence_chain = candidate.get("evidence_chain", [])

        # upstream: candidate explains alarms on both endpoints / downstream
        covered_alarms = {a.id for a in graph.get_alarms_for_node(root_cause)}
        upstream = round(min(len(covered_alarms) / max(total_alarms, 1), 1.0), 3)

        # time_lead: earliest alarm timestamp compared to candidate (simplified)
        time_lead = 0.5
        timestamps = [
            a.properties.get("timestamp", "")
            for a in alarms.values()
            if a.properties.get("timestamp")
        ]
        if timestamps:
            # If candidate is a link and alarms appear nearly simultaneously, it is plausible.
            time_lead = 0.9 if len(timestamps) >= 2 and self._time_spread(timestamps) <= 2 else 0.6

        # coverage: fraction of total alarms in the candidate chain
        coverage = round(min(len(evidence_chain) / max(total_alarms + 1, 1), 1.0), 3)

        # priority: severity of covered alarms
        severity_scores = {"critical": 1.0, "major": 0.75, "minor": 0.5, "warning": 0.25}
        severities = [
            alarms[alarm_id].properties.get("severity", "").lower()
            for alarm_id in covered_alarms
            if alarm_id in alarms
        ]
        priority = round(
            sum(severity_scores.get(s, 0.3) for s in severities) / max(len(severities), 1), 3
        )

        # case_sim: placeholder for case-base similarity (vector store integration later)
        case_sim = 0.5

        # conflict: low when candidate root cause type matches alarm pattern
        node_type, _ = graph.parse_node_id(root_cause)
        conflict = 0.9
        if has_fiber_cut and node_type == NodeType.LINK:
            conflict = 1.0
        elif node_type == NodeType.DEVICE and has_fiber_cut:
            conflict = 0.6

        return [upstream, time_lead, coverage, priority, case_sim, conflict]

    @staticmethod
    def _time_spread(timestamps: List[str]) -> float:
        try:
            from datetime import datetime

            parsed = []
            for ts in timestamps:
                try:
                    parsed.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                except ValueError:
                    continue
            if len(parsed) < 2:
                return float("inf")
            return (max(parsed) - min(parsed)).total_seconds()
        except Exception:
            return float("inf")
