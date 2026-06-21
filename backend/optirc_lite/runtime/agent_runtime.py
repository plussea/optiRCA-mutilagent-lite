from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel

from optirc_lite.skills.registry import SkillRegistry
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class AgentRuntime:
    """State-aware runtime that chooses skills inside a compiled workflow phase."""

    def __init__(self, skills: SkillRegistry, tools: ToolRegistry) -> None:
        self.skills = skills
        self.tools = tools

    async def run_phase(self, phase: str, state: AgentState) -> Dict[str, Any]:
        ranked = await self.skills.rank(state, phase)
        if not ranked:
            return {
                "status": f"{phase}_skipped",
                "decision_trace": self._append_decision(
                    state, phase, None, "no eligible skill", 0.0
                ),
            }

        skill_name, score = ranked[0]
        skill = self.skills.get(skill_name)
        output = await skill.run(state, self.tools)
        output = skill.output_schema.model_validate(output)
        phase_result = (
            output.result.model_dump()
            if isinstance(output.result, BaseModel)
            else output.result
        )

        return {
            phase: phase_result,
            "observations": [*state.get("observations", []), *output.observations],
            "decision_trace": self._append_decision(
                state,
                phase,
                skill_name,
                "highest can_handle score",
                score,
                output.next_suggestions,
            ),
            "tool_calls": [
                *state.get("tool_calls", []),
                {"phase": phase, "skill": skill_name, "tools": skill.required_tools},
            ],
        }

    @staticmethod
    def _append_decision(
        state: AgentState,
        phase: str,
        skill_name: str | None,
        reason: str,
        score: float,
        suggestions: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            *state.get("decision_trace", []),
            {
                "phase": phase,
                "skill": skill_name,
                "reason": reason,
                "score": score,
                "suggestions": suggestions or [],
                "at": datetime.now(timezone.utc).isoformat(),
            },
        ]
