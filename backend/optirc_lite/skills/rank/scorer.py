"""Root Cause Ranker submodules — Feature Scorer and Rank Aggregator."""

from typing import Any, Dict, List

from optirc_lite.storage.evidence_graph import (
    EvidenceGraph,
    NodeType,
)


class FeatureScorer:
    """Compute the six-dimensional feature vector for each candidate."""

    def score(
        self,
        candidates: List[Dict[str, Any]],
        state: Any,
    ) -> List[Dict[str, Any]]:
        fact_table: Dict[str, Any] = state.get("perception", {}) if isinstance(state, dict) else {}
        graph = EvidenceGraph()

        alarms = {n.id: n for n in graph.get_nodes(NodeType.ALARM)}
        total_alarms = max(len(alarms), fact_table.get("alarm_count", len(alarms)))
        alarm_types = [a.properties.get("alarm_type", "").lower() for a in alarms.values()]
        has_fiber_cut = any("los" in t for t in alarm_types)

        scored: List[Dict[str, Any]] = []
        for candidate in candidates:
            candidate["score_vector"] = self._compute_vector(
                candidate, alarms, total_alarms, has_fiber_cut, graph
            )
            scored.append(candidate)
        return scored

    def _compute_vector(
        self,
        candidate: Dict[str, Any],
        alarms: Dict[str, Any],
        total_alarms: int,
        has_fiber_cut: bool,
        graph: EvidenceGraph,
    ) -> List[float]:
        root_cause = candidate.get("root_cause", "")
        evidence_chain = candidate.get("evidence_chain", [])

        # upstream: candidate explains alarms on both endpoints / downstream
        covered_alarms = {a.id for a in graph.get_alarms_for_node(root_cause)}
        upstream = round(min(len(covered_alarms) / max(total_alarms, 1), 1.0), 3)

        # time_lead: earliest alarm timestamp compared to candidate (simplified)
        time_lead = 0.5
        timestamps = [
            a.properties.get("timestamp", "")
            for a in alarms.values()
            if a.properties.get("timestamp")
        ]
        if timestamps:
            time_lead = 0.9 if len(timestamps) >= 2 and self._time_spread(timestamps) <= 2 else 0.6

        # coverage: fraction of total alarms in the candidate chain
        coverage = round(min(len(evidence_chain) / max(total_alarms + 1, 1), 1.0), 3)

        # priority: severity of covered alarms
        severity_scores = {"critical": 1.0, "major": 0.75, "minor": 0.5, "warning": 0.25}
        severities = [
            alarms[alarm_id].properties.get("severity", "").lower()
            for alarm_id in covered_alarms
            if alarm_id in alarms
        ]
        priority = round(
            sum(severity_scores.get(s, 0.3) for s in severities) / max(len(severities), 1), 3
        )

        # case_sim: placeholder for case-base similarity (vector store integration later)
        case_sim = 0.5

        # conflict: low when candidate root cause type matches alarm pattern
        node_type, _ = graph.parse_node_id(root_cause)
        conflict = 0.9
        if has_fiber_cut and node_type == NodeType.LINK:
            conflict = 1.0
        elif node_type == NodeType.DEVICE and has_fiber_cut:
            conflict = 0.6

        return [upstream, time_lead, coverage, priority, case_sim, conflict]

    @staticmethod
    def _time_spread(timestamps: List[str]) -> float:
        try:
            from datetime import datetime

            parsed = []
            for ts in timestamps:
                try:
                    parsed.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                except ValueError:
                    continue
            if len(parsed) < 2:
                return float("inf")
            return (max(parsed) - min(parsed)).total_seconds()
        except Exception:
            return float("inf")


class RankAggregator:
    """Weighted fusion, conflict penalty, and Top-K sorting."""

    def aggregate(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        aggregated: List[Dict[str, Any]] = []
        for candidate in candidates:
            score_vector = candidate.get("score_vector", [])
            candidate["confidence"] = round(sum(score_vector) / max(len(score_vector), 1), 3)
            aggregated.append(candidate)

        aggregated.sort(key=lambda c: c.get("confidence", 0.0), reverse=True)
        return aggregated
