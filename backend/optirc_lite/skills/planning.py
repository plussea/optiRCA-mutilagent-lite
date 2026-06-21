import json

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import DefaultSkillInput, PlanningSkillOutput
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class RepairPlanningSkill:
    name = "planning.repair_plan"
    description = "Generate a conservative repair plan from diagnosis and SOP retrieval."
    required_tools = ["vector.search", "llm.generate_json"]
    input_schema = DefaultSkillInput
    output_schema = PlanningSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("diagnosis") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        diagnosis = state.get("diagnosis", {})
        root_cause = diagnosis.get("root_cause", "")
        sops = await tools.call("vector.search", query=root_cause, top_k=3, doc_type="sop")

        llm_plan = await self._try_llm_plan(tools, diagnosis, sops)
        if llm_plan:
            plan = llm_plan.get("final_plan", {})
            plan.setdefault("sops", sops)
            return {
                "result": {
                    "final_plan": plan,
                    "rollback_procedure": llm_plan.get(
                        "rollback_procedure",
                        "如修复动作引入异常，恢复原跳纤/配置并升级二线专家。",
                    ),
                    "llm_used": True,
                },
                "confidence": 0.78,
                "evidence": [f"匹配 SOP: {len(sops)} 条", f"根因: {root_cause or 'unknown'}"],
                "observations": [{"type": "planning", "value": llm_plan}],
                "next_suggestions": ["solution_validation.solution_critic"],
            }

        steps = [
            "确认告警范围和受影响业务，冻结非必要变更",
            "检查关联设备光功率、端口状态和近期告警时间线",
            "按根因建议执行现场检查或远程倒换",
            "执行修复后持续观察 15 分钟并确认告警清除",
        ]
        if "光纤" in root_cause or "光功率" in root_cause:
            steps.insert(2, "检查 ODF、尾纤、跳纤和上游光缆段")

        plan = {
            "title": "保守修复方案",
            "steps": steps,
            "estimated_time": "30-60 分钟",
            "required_resources": ["值班工程师", "现场巡检人员", "光功率计"],
            "sops": sops,
        }
        return {
            "result": {
                "final_plan": plan,
                "rollback_procedure": "如修复动作引入异常，恢复原跳纤/配置并升级二线专家。",
                "llm_used": False,
            },
            "confidence": 0.74,
            "evidence": [f"匹配 SOP: {len(sops)} 条", f"根因: {root_cause or 'unknown'}"],
            "observations": [{"type": "planning", "value": plan}],
            "next_suggestions": ["solution_validation.solution_critic"],
        }

    async def _try_llm_plan(
        self,
        tools: ToolRegistry,
        diagnosis: dict,
        sops: list[dict],
    ) -> dict | None:
        system = """你是光网络运维方案规划专家。
根据诊断结果和 SOP 输出 JSON：
{
  "final_plan": {
    "title": "方案标题",
    "steps": ["步骤1", "步骤2"],
    "estimated_time": "预计耗时",
    "required_resources": ["资源1"]
  },
  "rollback_procedure": "回滚步骤"
}
"""
        user = json.dumps({"diagnosis": diagnosis, "sops": sops}, ensure_ascii=False, indent=2)
        try:
            result = await tools.call(
                "llm.generate_json",
                system=system,
                user=user,
                temperature=0.2,
            )
        except Exception:
            return None
        return result if isinstance(result, dict) else None
