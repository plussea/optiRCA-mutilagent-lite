"""LLM-based counterfactual reasoning for the Critic."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from optirc_lite.tools.llm import llm_tool
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class LLMCounterfactualReviewer:
    """Optionally enrich critic rejection reasons using LLM counterfactual review.

    When an LLM is configured, the reviewer asks the model to check whether a
    rejected candidate could explain the unexplained alarms via alternative
    propagation paths. The LLM may either confirm the rejection, provide a
    softened note, or suggest a new fallback action. When the LLM is unavailable
    or fails, the original reject result is returned unchanged.
    """

    LLM_TIMEOUT_SECONDS = 8.0

    async def review(
        self,
        verdict: str,
        reasons: List[str],
        fallback_action: Optional[str],
        state: AgentState,
        tools: Optional[ToolRegistry],
    ) -> Dict[str, Any]:
        if verdict == "pass" or not self._llm_available(tools):
            return self._wrap(verdict, reasons, fallback_action, None)

        prompt = self._build_prompt(verdict, reasons, fallback_action, state)
        try:
            result = await asyncio.wait_for(
                tools.call(  # type: ignore[union-attr]
                    "llm.generate_json",
                    system=self._system_prompt(),
                    user=prompt,
                    temperature=0.2,
                ),
                timeout=self.LLM_TIMEOUT_SECONDS,
            )
        except Exception:
            return self._wrap(verdict, reasons, fallback_action, None)

        return self._apply_review(verdict, reasons, fallback_action, result)

    def _llm_available(self, tools: Optional[ToolRegistry]) -> bool:
        if tools is None or "llm.generate_json" not in tools.names():
            return False
        return llm_tool.enabled()

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are an expert optical transport network root-cause-analysis reviewer. "
            "A rule-based critic has rejected a root-cause candidate. Review the evidence "
            "and return strictly valid JSON. You may confirm the rejection, add nuance to "
            "the reasoning, or suggest a different fallback action. "
            "Do not wrap the response in markdown."
        )

    def _build_prompt(
        self,
        verdict: str,
        reasons: List[str],
        fallback_action: Optional[str],
        state: AgentState,
    ) -> str:
        evidence_graph = state.get("evidence_graph", {})
        perception = state.get("perception", {})
        candidates = state.get("candidates", [])
        return json.dumps(
            {
                "verdict": verdict,
                "reasons": reasons,
                "fallback_action": fallback_action,
                "candidates": candidates,
                "topology_and_alarms": {
                    "alarm_count": perception.get("alarm_count", 0),
                    "alarms": perception.get("alarms", []),
                    "evidence_graph": evidence_graph,
                },
                "instructions": (
                    "Return JSON with keys: 'verdict' ('pass' or 'reject'), 'reasons' (list of strings), "
                    "'fallback_action' ('FALLBACK_TO_JUDGE' or 'FALLBACK_TO_RANKER' or null), "
                    "'llm_review_note' (string explaining your reasoning). Keep the verdict 'pass' only "
                    "if you are confident the candidate explains all alarms."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

    def _apply_review(
        self,
        verdict: str,
        reasons: List[str],
        fallback_action: Optional[str],
        review: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(review, dict):
            return self._wrap(verdict, reasons, fallback_action, None)

        reviewed_verdict = review.get("verdict", verdict)
        reviewed_reasons = review.get("reasons", reasons)
        reviewed_action = review.get("fallback_action", fallback_action)
        note = review.get("llm_review_note")

        return self._wrap(reviewed_verdict, reviewed_reasons, reviewed_action, note)

    @staticmethod
    def _wrap(
        verdict: str,
        reasons: List[str],
        fallback_action: Optional[str],
        note: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "verdict": verdict,
            "reasons": reasons,
            "fallback_action": fallback_action,
            "llm_review_note": note,
        }
