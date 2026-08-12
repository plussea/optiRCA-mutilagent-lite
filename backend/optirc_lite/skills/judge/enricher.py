"""LLM-based hypothesis enrichment with rule fallback."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from optirc_lite.tools.llm import llm_tool
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class LLMHypothesisEnricher:
    """Optionally enrich judge candidates using LLM reasoning.

    When an LLM is configured, the enricher asks the model to review the
    candidate root causes against the topology and alarm evidence. It may
    adjust confidences, add missing candidates, or attach reasoning. When
    the LLM is unavailable or the call fails, it returns the original
    candidates unchanged (graceful rule fallback).
    """

    LLM_TIMEOUT_SECONDS = 8.0

    async def enrich(
        self,
        candidates: List[Dict[str, Any]],
        state: AgentState,
        tools: Optional[ToolRegistry],
    ) -> List[Dict[str, Any]]:
        if not candidates or not self._llm_available(tools):
            return candidates

        prompt = self._build_prompt(candidates, state)
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
            return candidates

        return self._apply_review(candidates, result)

    def _llm_available(self, tools: Optional[ToolRegistry]) -> bool:
        if tools is None or "llm.generate_json" not in tools.names():
            return False
        return llm_tool.enabled()

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are an expert optical transport network root-cause-analysis assistant. "
            "Review the candidate root causes below and return strictly valid JSON. "
            "You may adjust confidence scores, add plausible candidates that the rule-based "
            "generator missed, and provide concise reasoning. Do not wrap the response in markdown."
        )

    def _build_prompt(
        self,
        candidates: List[Dict[str, Any]],
        state: AgentState,
    ) -> str:
        evidence_graph = state.get("evidence_graph", {})
        perception = state.get("perception", {})
        return json.dumps(
            {
                "topology_and_alarms": {
                    "alarm_count": perception.get("alarm_count", 0),
                    "alarms": perception.get("alarms", []),
                    "evidence_graph": evidence_graph,
                },
                "current_candidates": candidates,
                "instructions": (
                    "Return JSON with keys: 'candidates' (list of updated candidates, each with "
                    "root_cause, confidence, evidence_chain, reasoning), 'added' (new candidates), "
                    "'removed' (list of root_cause strings to drop). Keep all unmodified candidates "
                    "in the 'candidates' list."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

    def _apply_review(
        self,
        candidates: List[Dict[str, Any]],
        review: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not isinstance(review, dict):
            return candidates

        removed = set(review.get("removed", []))
        updated = {c["root_cause"]: c for c in review.get("candidates", []) if isinstance(c, dict)}
        added = [c for c in review.get("added", []) if isinstance(c, dict)]

        enriched: List[Dict[str, Any]] = []
        for candidate in candidates:
            root_cause = candidate.get("root_cause", "")
            if root_cause in removed:
                continue
            if root_cause in updated:
                merged = {**candidate, **updated[root_cause]}
                merged["llm_enriched"] = True
                enriched.append(merged)
            else:
                enriched.append(candidate)

        for candidate in added:
            candidate.setdefault("llm_enriched", True)
            enriched.append(candidate)

        return enriched
