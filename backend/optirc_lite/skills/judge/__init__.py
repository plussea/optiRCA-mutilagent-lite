"""Propagation Judge — generates candidate root-cause propagation chains."""

from typing import Any, Dict, List

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.judge.enricher import LLMHypothesisEnricher
from optirc_lite.skills.judge.generator import ChainHypothesisGenerator
from optirc_lite.skills.judge.validator import ChainValidator
from optirc_lite.skills.schemas import DefaultSkillInput, JudgeSkillOutput
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class PropagationJudgeSkill:
    name = "judge.root_cause_judge"
    description = "Generate candidate root-cause propagation chains from the evidence graph."
    required_tools = []
    input_schema = DefaultSkillInput
    output_schema = JudgeSkillOutput

    def __init__(self) -> None:
        self._generator = ChainHypothesisGenerator()
        self._validator = ChainValidator()
        self._enricher = LLMHypothesisEnricher()

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("perception") and state.get("evidence_graph") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        raw_candidates = self._generator.generate(state)
        validated = self._validator.validate(raw_candidates, state)
        candidates = await self._enricher.enrich(validated, state, tools)

        return {
            "result": {"candidates": candidates},
            "confidence": 0.8 if candidates else 0.2,
            "evidence": [f"生成 {len(candidates)} 条候选传播链"],
            "observations": [{"type": "judge_candidates", "value": {"count": len(candidates)}}],
            "next_suggestions": ["rank.candidate_ranker"],
        }
