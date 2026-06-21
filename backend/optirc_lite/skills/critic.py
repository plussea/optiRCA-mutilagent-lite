from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import (
    DefaultSkillInput,
    SolutionValidationSkillOutput,
    ValidationSkillOutput,
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
