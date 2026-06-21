from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import ClosureSkillOutput, DefaultSkillInput
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class KnowledgeClosureSkill:
    name = "closure.knowledge"
    description = "Persist approved case knowledge to local vector and graph stores."
    required_tools = ["knowledge.save_case"]
    input_schema = DefaultSkillInput
    output_schema = ClosureSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("human_decision") == "approved" else 0.2

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        diagnosis = state.get("diagnosis", {})
        perception = state.get("perception", {})
        saved = await tools.call(
            "knowledge.save_case",
            session_id=state["session_id"],
            root_cause=diagnosis.get("root_cause", "unknown"),
            device_ids=perception.get("devices", []),
        )
        summary = {
            "stored": saved.get("stored", False),
            "summary": (
                f"会话 {state['session_id']} 已闭环: "
                f"{diagnosis.get('root_cause', 'unknown')}"
            ),
        }
        return {
            "result": summary,
            "confidence": 1.0,
            "evidence": [saved.get("content", "")],
            "observations": [{"type": "closure", "value": summary}],
            "next_suggestions": [],
        }
