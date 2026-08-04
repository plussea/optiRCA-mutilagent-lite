"""Evaluator — offline regression and error attribution for diagnosis cases."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from optirc_lite.storage.sqlite_store import store


class Evaluator:
    """Compute multi-objective metrics and error attribution over diagnosis dossiers."""

    def evaluate(
        self,
        dossier_ids: List[str],
        evaluation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run regression over the given dossier ids and produce a report."""
        evaluation_id = evaluation_id or f"EVAL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        cases: List[Dict[str, Any]] = []

        for dossier_id in dossier_ids:
            dossier = store.get_session(dossier_id)
            if dossier is None:
                continue
            case_result = self._evaluate_case(dossier)
            cases.append(case_result)

        metrics = self._aggregate(cases)
        report = {
            "evaluation_id": evaluation_id,
            "status": "completed",
            "dossier_ids": dossier_ids,
            "metrics": metrics,
            "cases": cases,
            "error_attribution": self._aggregate_attribution(cases),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        store.upsert_session(evaluation_id, "completed", report)
        return report

    def _evaluate_case(self, dossier: Dict[str, Any]) -> Dict[str, Any]:
        output = dossier.get("output_layer", {})
        feedback = dossier.get("feedback_layer", {})
        metadata = dossier.get("metadata", {})

        predicted = output.get("root_cause", {}).get("root_cause", "unknown")
        ground_truth = (feedback.get("ground_truth") or {}).get("root_cause", "unknown")

        candidates = dossier.get("intermediate_layer", {}).get("hypotheses", [])
        candidate_roots = [c.get("root_cause", "unknown") for c in candidates]

        top1_match = predicted != "unknown" and predicted == ground_truth
        top3_match = ground_truth in candidate_roots[:3] if candidate_roots else False

        critic_verdict = metadata.get("critic_verdict")
        degradation_reason = metadata.get("degradation_reason")
        requires_human_review = output.get("requires_human_review", True)

        # Critic quality flags
        critic_recalled = False
        critic_false_reject = False
        if critic_verdict == "reject" and degradation_reason in {"max_fallback_exceeded", "critic_timeout"}:
            # Critic rejected what later turned out to be the true root cause.
            critic_false_reject = top1_match or top3_match
            critic_recalled = not (top1_match or top3_match)
        elif critic_verdict == "pass" and not top1_match:
            critic_recalled = False

        latency_ms = self._estimate_latency(dossier)

        return {
            "dossier_id": dossier.get("dossier_id"),
            "predicted": predicted,
            "ground_truth": ground_truth,
            "top1_match": top1_match,
            "top3_match": top3_match,
            "degraded": bool(degradation_reason),
            "degradation_reason": degradation_reason,
            "requires_human_review": requires_human_review,
            "critic_verdict": critic_verdict,
            "critic_false_reject": critic_false_reject,
            "critic_recalled": critic_recalled,
            "latency_ms": latency_ms,
            "error_attribution": self._attribute_error(
                top1_match, top3_match, degradation_reason, candidates, dossier
            ),
        }

    def _attribute_error(
        self,
        top1_match: bool,
        top3_match: bool,
        degradation_reason: Optional[str],
        candidates: List[Dict[str, Any]],
        dossier: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Return structured error attribution pointing to a strategy lever.

        Degradation reasons are attributed first because a degraded output is a
        failure mode even if the predicted root cause happens to match ground
        truth.
        """
        if degradation_reason == "judge_timeout":
            return [{"lever": "judge", "reason": "Judge did not generate the true root cause"}]
        if degradation_reason == "ranker_timeout":
            return [{"lever": "rank", "reason": "Ranker failed to score or order candidates"}]
        if degradation_reason in {"critic_timeout", "max_fallback_exceeded"}:
            return [{"lever": "critic", "reason": "Critic rejected or could not validate the true root cause"}]
        if degradation_reason == "agent_failure":
            return [{"lever": "prompt", "reason": "Agent failed to produce a usable result"}]

        if top1_match:
            return []

        if top3_match and not top1_match:
            return [{"lever": "weights", "reason": "True root cause appeared in Top-3 but was not ranked first"}]

        if candidates:
            return [{"lever": "judge", "reason": "True root cause not among generated candidates"}]

        return [{"lever": "cases", "reason": "No candidates produced"}]

    def _estimate_latency(self, dossier: Dict[str, Any]) -> float:
        """Estimate latency from decision trace timestamps when available."""
        traces = dossier.get("intermediate_layer", {}).get("decision_trace", [])
        if len(traces) < 2:
            return 0.0
        try:
            start = datetime.fromisoformat(traces[0].get("at", ""))
            end = datetime.fromisoformat(traces[-1].get("at", ""))
            return (end - start).total_seconds() * 1000.0
        except Exception:
            return 0.0

    def _aggregate(self, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(cases)
        if total == 0:
            return {
                "top1_acc": 0.0,
                "top3_recall": 0.0,
                "critic_recall": 0.0,
                "critic_false_reject": 0.0,
                "avg_latency_ms": 0.0,
            }

        top1_hits = sum(1 for c in cases if c["top1_match"])
        top3_hits = sum(1 for c in cases if c["top3_match"])
        critic_recalls = sum(1 for c in cases if c["critic_recalled"])
        false_rejects = sum(1 for c in cases if c["critic_false_reject"])
        latencies = [c["latency_ms"] for c in cases]

        return {
            "top1_acc": round(top1_hits / total, 4),
            "top3_recall": round(top3_hits / total, 4),
            "critic_recall": round(critic_recalls / total, 4),
            "critic_false_reject": round(false_rejects / total, 4),
            "avg_latency_ms": round(sum(latencies) / total, 2) if latencies else 0.0,
        }

    def _aggregate_attribution(self, cases: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for case in cases:
            for item in case.get("error_attribution", []):
                lever = item.get("lever", "unknown")
                counts[lever] = counts.get(lever, 0) + 1
        return counts


evaluator = Evaluator()
