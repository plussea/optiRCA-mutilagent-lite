from typing import Any, Dict, List, Set

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import (
    CriticSkillOutput,
    DefaultSkillInput,
    SolutionValidationSkillOutput,
    ValidationSkillOutput,
)
from optirc_lite.storage.evidence_graph import (
    EvidenceGraph,
    NodeType,
)
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class DiagnosisCriticSkill:
    name = "validation.diagnosis_critic"
    description = "Validate diagnosis confidence, evidence completeness, and escalation need."
    required_tools: list[str] = []
    input_schema = DefaultSkillInput
    output_schema = ValidationSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("diagnosis") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        diagnosis = state.get("diagnosis", {})
        confidence = float(diagnosis.get("confidence", 0))
        evidence = diagnosis.get("evidence", [])
        passed = confidence >= 0.6 and len(evidence) >= 2
        suggested_action = "proceed" if passed else "needs_human"
        notes = "诊断证据和置信度满足进入规划条件" if passed else "诊断置信度或证据不足，建议人工关注"
        return {
            "result": {
                "validation_passed": passed,
                "score": confidence,
                "notes": notes,
                "suggested_action": suggested_action,
            },
            "confidence": confidence,
            "evidence": evidence,
            "observations": [{"type": "critic", "passed": passed, "notes": notes}],
            "next_suggestions": ["planning.repair_plan"] if passed else ["human_review"],
        }


class SolutionCriticSkill:
    name = "solution_validation.solution_critic"
    description = "Validate repair plan feasibility and risk."
    required_tools: list[str] = []
    input_schema = DefaultSkillInput
    output_schema = SolutionValidationSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("planning") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        plan = state.get("planning", {}).get("final_plan", {})
        steps = plan.get("steps", [])
        resources = plan.get("required_resources", [])
        valid = bool(steps) and bool(resources)
        risk_level = "medium" if valid else "high"
        notes = "方案可执行，但仍建议人工批准后实施" if valid else "方案缺少步骤或资源约束"
        return {
            "result": {
                "solution_valid": valid,
                "risk_level": risk_level,
                "notes": notes,
                "needs_replan": not valid,
            },
            "confidence": 0.72 if valid else 0.35,
            "evidence": [f"步骤数: {len(steps)}", f"资源数: {len(resources)}"],
            "observations": [{"type": "solution_critic", "valid": valid, "risk": risk_level}],
            "next_suggestions": ["human_review"],
        }


class RefactorCriticSkill:
    name = "critic.diagnosis_critic"
    description = "Review top-K root-cause candidates with three counterfactual challenges."
    required_tools: list[str] = []
    input_schema = DefaultSkillInput
    output_schema = CriticSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("candidates") and state.get("evidence_graph") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        candidates: List[Dict[str, Any]] = state.get("candidates", [])
        graph = EvidenceGraph()

        all_alarm_ids = {n.id for n in graph.get_nodes(NodeType.ALARM)}

        if not candidates:
            return self._reject("no candidates provided", "FALLBACK_TO_JUDGE")

        top_candidate = candidates[0]
        root_cause = top_candidate.get("root_cause", "")
        node_type, _ = graph.parse_node_id(root_cause)

        explained = self._explained_alarms(top_candidate, graph)

        # Any alarm explicitly named in the evidence chain is also considered explained
        evidence_chain = top_candidate.get("evidence_chain", [])
        chain_text = " ".join(str(line) for line in evidence_chain)
        for alarm_id in all_alarm_ids:
            if alarm_id in chain_text:
                explained.add(alarm_id)

        unexplained = all_alarm_ids - explained
        multi_cluster_reason = None
        if len(clusters := graph.alarm_clusters()) > 1:
            uncovered = [c for c in clusters if not (c <= explained)]
            if uncovered:
                multi_cluster_reason = (
                    f"detected {len(uncovered)} additional alarm cluster(s) "
                    "unexplained by top candidate"
                )

        if unexplained:
            # Prefer the more specific multi-cluster reason when it covers all unexplained alarms.
            if multi_cluster_reason and unexplained <= set().union(*uncovered):
                return self._reject(multi_cluster_reason, "FALLBACK_TO_JUDGE")
            return self._reject(
                f"top candidate leaves {len(unexplained)} alarm(s) unexplained",
                "FALLBACK_TO_JUDGE",
            )

        if multi_cluster_reason:
            return self._reject(multi_cluster_reason, "FALLBACK_TO_JUDGE")

        # Challenge #2: for Link candidates, both endpoints must have consistent LOS-type alarms.
        if node_type == NodeType.LINK:
            alarms_a, alarms_b = graph.get_link_endpoint_alarms(root_cause)
            los_types = {"los", "mut_los"}
            a_has_los = any(
                graph.get_node(a).properties.get("alarm_type", "").lower() in los_types
                for a in alarms_a
                if graph.get_node(a)
            )
            b_has_los = any(
                graph.get_node(b).properties.get("alarm_type", "").lower() in los_types
                for b in alarms_b
                if graph.get_node(b)
            )
            if alarms_a and alarms_b and not (a_has_los and b_has_los):
                return self._reject(
                    "link candidate lacks bidirectional LOS consistency",
                    "FALLBACK_TO_RANKER",
                )

        # Challenge #3: detect disjoint alarm clusters that suggest a missed multi-root cause.
        clusters = graph.alarm_clusters()
        if len(clusters) > 1:
            explained_set = explained
            uncovered_clusters = [
                cluster for cluster in clusters if not (cluster <= explained_set)
            ]
            if uncovered_clusters:
                return self._reject(
                    f"detected {len(uncovered_clusters)} additional alarm cluster(s) not explained by top candidate",
                    "FALLBACK_TO_JUDGE",
                )

        return {
            "result": {
                "verdict": "pass",
                "reasons": ["top candidate explains all observed alarms"],
                "fallback_action": None,
            },
            "confidence": top_candidate.get("confidence", 0.0),
            "evidence": ["Critic passed: all alarms explained by top candidate"],
            "observations": [{"type": "critic_pass", "value": {"candidate": top_candidate["root_cause"]}}],
            "next_suggestions": [],
        }

    def _explained_alarms(self, candidate: Dict[str, Any], graph: EvidenceGraph) -> Set[str]:
        root_cause = candidate.get("root_cause", "")
        node_type, _ = graph.parse_node_id(root_cause)
        explained: Set[str] = set()

        if node_type in {NodeType.DEVICE, NodeType.PORT, NodeType.LINK}:
            explained = {a.id for a in graph.get_alarms_for_node(root_cause)}

        return explained

    def _reject(self, reason: str, action: str) -> SkillOutput:
        return {
            "result": {
                "verdict": "reject",
                "reasons": [reason],
                "fallback_action": action,
            },
            "confidence": 0.0,
            "evidence": [f"Critic rejected: {reason}"],
            "observations": [{"type": "critic_reject", "value": {"reason": reason, "fallback_action": action}}],
            "next_suggestions": [action.lower().replace("fallback_to_", "")],
        }
