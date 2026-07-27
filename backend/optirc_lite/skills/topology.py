"""Topology Builder skill — constructs the heterogeneous evidence graph."""

from typing import Any, Dict, List

from optirc_lite.skills.base import SkillOutput
from optirc_lite.skills.schemas import DefaultSkillInput, PerceptionSkillOutput
from optirc_lite.storage.evidence_graph import (
    EdgeType,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    NodeType,
)
from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class TopologyBuilderSkill:
    name = "topology.topology_builder"
    description = "Build a heterogeneous evidence graph from topology JSON and alarm fact table."
    required_tools = []
    input_schema = DefaultSkillInput
    output_schema = PerceptionSkillOutput

    async def can_handle(self, state: AgentState) -> float:
        return 1.0 if state.get("perception") and state.get("topology") else 0.0

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        fact_table: Dict[str, Any] = state["perception"]
        topology: Dict[str, Any] = state["topology"]

        graph = EvidenceGraph()
        graph.init()

        device_nodes = self._build_devices(topology, graph)
        port_nodes = self._build_ports(topology, graph, device_nodes)
        self._build_links(topology, graph, port_nodes)
        self._build_alarms(fact_table, graph)

        return {
            "result": {
                "input_name": fact_table.get("input_name", "unknown"),
                "alarm_count": fact_table.get("alarm_count", 0),
                "alarms": fact_table.get("alarms", []),
                "headers": fact_table.get("headers", []),
                "first_row": fact_table.get("alarms", [{}])[0],
                "alarm_types": fact_table.get("alarm_types", []),
                "devices": list(device_nodes.keys()),
                "primary_alarm": fact_table.get("primary_alarm", "unknown"),
                "primary_device": fact_table.get("primary_device", ""),
                "description": fact_table.get("description", ""),
            },
            "confidence": 0.9,
            "evidence": [f"构建 {len(device_nodes)} 个设备节点", f"关联 {fact_table.get('alarm_count', 0)} 条告警"],
            "observations": [{"type": "evidence_graph_built", "value": {"node_count": len(graph.get_nodes())}}],
            "next_suggestions": ["diagnosis.propagation_judge"],
        }

    def _build_devices(self, topology: Dict[str, Any], graph: EvidenceGraph) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for device in topology.get("devices", []):
            device_id = device["device_id"]
            node_id = f"dev:{device_id}"
            graph.add_node(
                EvidenceNode(
                    id=node_id,
                    type=NodeType.DEVICE,
                    device_id=device_id,
                    device_type=device.get("type", "unknown"),
                    vendor=device.get("vendor"),
                    location=device.get("location"),
                    layer=device.get("layer"),
                )
            )
            mapping[device_id] = node_id
        return mapping

    def _build_ports(
        self,
        topology: Dict[str, Any],
        graph: EvidenceGraph,
        device_nodes: Dict[str, str],
    ) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for port in topology.get("ports", []):
            port_id = port["port_id"]
            node_id = f"port:{port_id}"
            device_id = port.get("device_id")
            graph.add_node(
                EvidenceNode(
                    id=node_id,
                    type=NodeType.PORT,
                    port_id=port_id,
                    device_id=device_id,
                    direction=port.get("direction"),
                    rate=port.get("rate"),
                    status=port.get("status"),
                )
            )
            if device_id and device_id in device_nodes:
                graph.add_edge(
                    EvidenceEdge(
                        source=device_nodes[device_id],
                        target=node_id,
                        type=EdgeType.TOPOLOGY,
                        confidence=1.0,
                    )
                )
            mapping[port_id] = node_id
        return mapping

    def _build_links(
        self,
        topology: Dict[str, Any],
        graph: EvidenceGraph,
        port_nodes: Dict[str, str],
    ) -> None:
        for link in topology.get("links", []):
            link_id = link["link_id"]
            endpoint_a = link.get("endpoint_a")
            endpoint_b = link.get("endpoint_b")
            node_id = f"link:{link_id}"
            graph.add_node(
                EvidenceNode(
                    id=node_id,
                    type=NodeType.LINK,
                    link_id=link_id,
                    endpoint_a=endpoint_a,
                    endpoint_b=endpoint_b,
                    length_km=link.get("length_km"),
                    loss_db=link.get("loss_db"),
                )
            )
            if endpoint_a in port_nodes:
                graph.add_edge(
                    EvidenceEdge(
                        source=port_nodes[endpoint_a],
                        target=node_id,
                        type=EdgeType.TOPOLOGY,
                        confidence=1.0,
                        distance_km=link.get("length_km"),
                    )
                )
            if endpoint_b in port_nodes:
                graph.add_edge(
                    EvidenceEdge(
                        source=port_nodes[endpoint_b],
                        target=node_id,
                        type=EdgeType.TOPOLOGY,
                        confidence=1.0,
                        distance_km=link.get("length_km"),
                    )
                )

    def _build_alarms(self, fact_table: Dict[str, Any], graph: EvidenceGraph) -> None:
        alarms: List[Dict[str, Any]] = fact_table.get("alarms", [])
        device_ids = {n.properties.get("device_id") for n in graph.get_nodes(NodeType.DEVICE)}
        for alarm in alarms:
            alarm_id = alarm.get("alarm_id")
            node_id = f"alm:{alarm_id}"
            port_id = alarm.get("port_id")
            device_id = alarm.get("device_id")
            graph.add_node(
                EvidenceNode(
                    id=node_id,
                    type=NodeType.ALARM,
                    alarm_id=alarm_id,
                    alarm_type=alarm.get("type"),
                    severity=alarm.get("severity"),
                    timestamp=alarm.get("timestamp"),
                    port_id=port_id,
                    device_id=device_id,
                    raw_text=alarm.get("raw_text"),
                )
            )
            target = None
            if port_id:
                target = f"port:{port_id}"
            elif device_id and device_id in device_ids:
                target = f"dev:{device_id}"

            if target:
                try:
                    graph.add_edge(
                        EvidenceEdge(
                            source=node_id,
                            target=target,
                            type=EdgeType.BELONGS_TO,
                            confidence=1.0,
                        )
                    )
                except ValueError:
                    # Target not in topology; alarm still exists as orphan
                    pass
