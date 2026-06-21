import json

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import DefaultSkillInput, DiagnosisSkillOutput
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class RootCauseDiagnosisSkill:
    name = "diagnosis.root_cause"
    description = "Fuse alarm summary, local knowledge, topology hints, and optional LLM RCA."
    required_tools = ["vector.search", "graph.neighbors", "llm.generate_json"]
    input_schema = DefaultSkillInput
    output_schema = DiagnosisSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("perception") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        perception = state.get("perception", {})
        query = " ".join(
            [
                perception.get("primary_alarm", ""),
                perception.get("primary_device", ""),
                perception.get("description", ""),
                " ".join(perception.get("alarm_types", [])),
            ]
        ).strip()
        docs = await tools.call("vector.search", query=query, top_k=4)
        graph = await tools.call("graph.neighbors", node_ids=perception.get("devices", []), depth=1)

        llm_result = await self._try_llm_diagnosis(tools, perception, docs, graph)
        if llm_result:
            confidence = float(llm_result.get("confidence", 0.0))
            evidence = [str(item) for item in llm_result.get("evidence", [])]
            return {
                "result": {
                    "root_cause": llm_result.get("root_cause", "unknown"),
                    "confidence": confidence,
                    "evidence": evidence,
                    "recommended_action": llm_result.get("recommended_action", ""),
                    "retrieved_docs": docs,
                    "topology_context": graph,
                    "llm_used": True,
                },
                "confidence": confidence,
                "evidence": evidence,
                "observations": [
                    {"type": "retrieval", "docs": docs},
                    {"type": "topology", "graph": graph},
                    {"type": "llm_diagnosis", "value": llm_result},
                ],
                "next_suggestions": ["validation.diagnosis_critic"],
            }

        root_cause, confidence, action = self._heuristic_diagnosis(perception)
        evidence = [
            f"主告警: {perception.get('primary_alarm', 'unknown')}",
            f"影响设备数: {len(perception.get('devices', []))}",
            f"检索到知识文档: {len(docs)} 条",
        ]
        if graph.get("nodes"):
            evidence.append(f"拓扑邻居节点: {len(graph['nodes'])} 个")

        return {
            "result": {
                "root_cause": root_cause,
                "confidence": confidence,
                "evidence": evidence,
                "recommended_action": action,
                "retrieved_docs": docs,
                "topology_context": graph,
                "llm_used": False,
            },
            "confidence": confidence,
            "evidence": evidence,
            "observations": [{"type": "retrieval", "docs": docs}, {"type": "topology", "graph": graph}],
            "next_suggestions": ["validation.diagnosis_critic"],
        }

    async def _try_llm_diagnosis(
        self,
        tools: ToolRegistry,
        perception: dict,
        docs: list[dict],
        graph: dict,
    ) -> dict | None:
        system = """你是光网络运维根因分析专家。
根据告警摘要、知识检索结果和拓扑上下文输出 JSON：
{
  "root_cause": "最可能根因",
  "confidence": 0.0,
  "evidence": ["证据1", "证据2"],
  "recommended_action": "建议动作"
}
"""
        user = json.dumps(
            {
                "perception": perception,
                "retrieved_docs": docs,
                "topology_context": graph,
            },
            ensure_ascii=False,
            indent=2,
        )
        try:
            result = await tools.call(
                "llm.generate_json",
                system=system,
                user=user,
                temperature=0.1,
            )
        except Exception:
            return None
        return result if isinstance(result, dict) else None

    @staticmethod
    def _heuristic_diagnosis(perception: dict) -> tuple[str, float, str]:
        alarm_text = " ".join(perception.get("alarm_types", [])).lower()
        if any(word in alarm_text for word in ["los", "mut_los", "光功率", "光纤", "断纤"]):
            return (
                "疑似光纤中断或链路光功率异常",
                0.78,
                "检查光功率、ODF 跳纤、尾纤连接和上游光缆段",
            )
        if any(word in alarm_text for word in ["crc", "fec", "误码"]):
            return (
                "疑似光模块劣化或连接器污染导致误码",
                0.70,
                "清洁连接器，复测光功率，必要时更换光模块",
            )
        return (
            "告警模式不明确，需要结合现场和历史案例继续排查",
            0.45,
            "补充设备日志、拓扑关系和近期变更记录",
        )
