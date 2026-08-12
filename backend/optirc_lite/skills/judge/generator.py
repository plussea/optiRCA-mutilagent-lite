"""Chain Hypothesis Generator — enumerates candidate root-cause propagation chains."""

from typing import Any, Dict, List, Set

from optirc_lite.storage.evidence_graph import EvidenceGraph, NodeType
from optirc_lite.workflow.state import AgentState


class ChainHypothesisGenerator:
    """Generate candidate root-cause propagation chains from the evidence graph."""

    def generate(self, state: AgentState) -> List[Dict[str, Any]]:
        fact_table: Dict[str, Any] = state.get("perception", {})
        graph = EvidenceGraph()

        alarms = {n.id: n for n in graph.get_nodes(NodeType.ALARM)}
        links = graph.get_nodes(NodeType.LINK)
        devices = graph.get_nodes(NodeType.DEVICE)

        candidates: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        # Link candidates: a broken link often produces LOS/MUT_LOS on both endpoints.
        ports = graph.get_nodes(NodeType.PORT)
        port_by_property = {p.properties.get("port_id", p.id): p.id for p in ports}

        for link in links:
            link_id = link.properties.get("link_id", link.id)
            key = f"link:{link_id}"
            chain_alarms: List[str] = []

            for endpoint in (link.properties.get("endpoint_a"), link.properties.get("endpoint_b")):
                if not endpoint:
                    continue
                port_node_id = port_by_property.get(endpoint, f"port:{endpoint}")
                for alarm in graph.get_alarms_for_node(port_node_id):
                    alarm_type = alarm.properties.get("alarm_type", "alarm")
                    chain_alarms.append(f"{alarm_type} @ {endpoint}")

            # Score link candidates: favor links whose endpoint alarms include
            # the most severe physical-layer LOS pair (OTS/OSC/MUT_LOS).
            endpoint_alarm_types = {item.split(" @ ")[0].lower() for item in chain_alarms}
            physical_los_count = sum(
                1 for t in endpoint_alarm_types if "los" in t and ("ots" in t or "osc" in t or "mut_los" in t)
            )
            if physical_los_count >= 2:
                confidence = 0.95
            elif any("los" in t for t in endpoint_alarm_types):
                confidence = 0.8
            else:
                confidence = 0.7

            seen.add(key)
            candidates.append(
                {
                    "root_cause": key,
                    "confidence": confidence,
                    "score_vector": [],
                    "evidence_chain": [
                        f"candidate root cause: {key}",
                        f"endpoints: {link.properties.get('endpoint_a') or '-'} / {link.properties.get('endpoint_b') or '-'}",
                        *chain_alarms,
                    ],
                }
            )

        # Device candidates for any alarm-bearing device not already covered by a link.
        for device in devices:
            _, device_id = graph.parse_node_id(device.id)
            alarm_ids = {a.id for a in graph.get_alarms_for_node(device.id)}
            if not alarm_ids:
                continue
            key = f"dev:{device_id}"
            if key in seen:
                continue
            seen.add(key)
            chain_alarms = [
                f"{alarms[a].properties.get('alarm_type', 'alarm')} @ {device_id}"
                for a in alarm_ids
                if a in alarms
            ]
            candidates.append(
                {
                    "root_cause": key,
                    "confidence": 0.6,
                    "score_vector": [],
                    "evidence_chain": [
                        f"candidate root cause: {key}",
                        *chain_alarms,
                    ],
                }
            )

        # Fallback: if the graph is empty, return a single degraded candidate.
        if not candidates and fact_table.get("alarm_count", 0) == 0:
            candidates.append(
                {
                    "root_cause": "unknown",
                    "confidence": 0.0,
                    "score_vector": [],
                    "evidence_chain": ["no alarms or topology available"],
                }
            )

        return candidates
