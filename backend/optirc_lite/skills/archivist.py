"""Case Archivist — assembles and persists five-layer Diagnosis Dossiers."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from optirc_lite.config import settings
from optirc_lite.storage.sqlite_store import store
from optirc_lite.storage.vector_store import vector_store


class CaseArchivist:
    """Archive closed diagnoses as structured dossiers and propagation templates."""

    def archive(
        self,
        dossier_id: str,
        session_id: str,
        input_payload: Dict[str, Any],
        evidence_graph: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        top_candidate: Optional[Dict[str, Any]],
        critic_verdict: Optional[str],
        degradation_reason: Optional[str],
        confidence: float,
        requires_human_review: bool,
        human_decision: Optional[str] = None,
        human_notes: Optional[str] = None,
        ground_truth: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a five-layer dossier, persist it, and index a propagation template."""
        dossier = self._build_dossier(
            dossier_id=dossier_id,
            session_id=session_id,
            input_payload=input_payload,
            evidence_graph=evidence_graph,
            candidates=candidates,
            top_candidate=top_candidate,
            critic_verdict=critic_verdict,
            degradation_reason=degradation_reason,
            confidence=confidence,
            requires_human_review=requires_human_review,
            human_decision=human_decision,
            human_notes=human_notes,
            ground_truth=ground_truth,
        )

        status = "success" if not requires_human_review and not degradation_reason else "degraded"
        if human_decision in {
            "approved",
            "rejected",
            "escalated",
            "confirmed",
            "corrected",
            "expert_review_requested",
        }:
            status = human_decision

        store.upsert_dossier(
            dossier_id=dossier_id,
            session_id=session_id,
            status=status,
            input_payload=input_payload,
            evidence_graph=evidence_graph,
            top_candidate=top_candidate,
            critic_verdict=critic_verdict,
            degradation_reason=degradation_reason,
            confidence=confidence,
            requires_human_review=requires_human_review,
        )

        # Persist full five-layer dossier in session store for retrieval endpoint.
        store.upsert_session(dossier_id, status, dossier)

        self._index_template(dossier)
        return dossier

    def _build_dossier(
        self,
        dossier_id: str,
        session_id: str,
        input_payload: Dict[str, Any],
        evidence_graph: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        top_candidate: Optional[Dict[str, Any]],
        critic_verdict: Optional[str],
        degradation_reason: Optional[str],
        confidence: float,
        requires_human_review: bool,
        human_decision: Optional[str],
        human_notes: Optional[str],
        ground_truth: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "dossier_id": dossier_id,
            "session_id": session_id,
            "input_layer": {
                "filename": input_payload.get("filename"),
                "topology": input_payload.get("topology"),
                "submitted_at": now,
            },
            "intermediate_layer": {
                "hypotheses": candidates,
                "validation_results": [],
                "scores": [c.get("score_vector", []) for c in candidates],
                "critic_challenges": [],
                "evidence_graph": evidence_graph,
            },
            "output_layer": {
                "root_cause": top_candidate,
                "confidence": confidence,
                "requires_human_review": requires_human_review,
                "suggested_action": "proceed" if top_candidate and not requires_human_review else "needs_human",
            },
            "feedback_layer": {
                "human_decision": human_decision,
                "human_notes": human_notes,
                "ground_truth": ground_truth,
            },
            "metadata": {
                "critic_verdict": critic_verdict,
                "degradation_reason": degradation_reason,
                "archived_at": now,
            },
        }

    def _index_template(self, dossier: Dict[str, Any]) -> None:
        top = dossier.get("output_layer", {}).get("root_cause") or {}
        if not top or not top.get("root_cause"):
            return

        is_positive = dossier.get("feedback_layer", {}).get("human_decision") in {
            "approved",
            "confirmed",
            None,
        }
        if not is_positive:
            return

        evidence_chain = top.get("evidence_chain", [])
        content = f"Root cause: {top['root_cause']}. Evidence: {'; '.join(evidence_chain)}"
        vector_store.add(
            content=content,
            metadata={
                "id": dossier["dossier_id"],
                "type": "case_template",
                "root_cause": top["root_cause"],
                "confidence": top.get("confidence", 0.0),
                "session_id": dossier["session_id"],
            },
        )


archivist = CaseArchivist()
