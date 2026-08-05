"""Root Cause Ranker — scores and sorts candidate propagation chains."""

from typing import Any, Dict, List

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.rank.scorer import FeatureScorer, RankAggregator
from optirc_lite.skills.schemas import DefaultSkillInput, RankSkillOutput
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class RootCauseRankerSkill:
    name = "rank.candidate_ranker"
    description = "Score candidate root causes with a six-dimensional vector and rank them."
    required_tools = []
    input_schema = DefaultSkillInput
    output_schema = RankSkillOutput

    def __init__(self) -> None:
        self._scorer = FeatureScorer()
        self._aggregator = RankAggregator()

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("judge") and state.get("evidence_graph") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        judge_result: Dict[str, Any] = state.get("judge", {})
        candidates: List[Dict[str, Any]] = list(judge_result.get("candidates", []))

        scored = self._scorer.score(candidates, state)
        ranked = self._aggregator.aggregate(scored)

        return {
            "result": {"candidates": ranked},
            "confidence": 0.9 if ranked else 0.2,
            "evidence": [f"排序后返回 {len(ranked)} 个候选根因"],
            "observations": [{"type": "rank_candidates", "value": {"count": len(ranked)}}],
            "next_suggestions": ["critic.diagnosis_critic"],
        }
