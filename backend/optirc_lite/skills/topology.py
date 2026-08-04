"""Topology Builder skill — constructs the heterogeneous evidence graph."""

from typing import Any, Dict, List, Set

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
        self._infer_missing_links(topology, graph, port_nodes)
        self._build_alarms(fact_table, graph)
        graph.build_propagates_edges()
        self._mark_isolated_nodes(graph)

        return {
            "result": {
                "input_name": fact_table.get("input_name", "unknown"),
                "alarm_count": fact_table.get("alarm_count", 0),
                "alarms": fact_table.get("alarms", []),
                "headers": fact_table.get("headers", []),
                "first_row": fact_table.get("first_row") or (fact_table.get("alarms", [{}])[0] if fact_table.get("alarms") else {}),
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
            node_id = device_id if device_id.startswith("dev:") else f"dev:{device_id}"
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
            node_id = port_id if port_id.startswith("port:") else f"port:{port_id}"
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
                        inferred=False,
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
            node_id = link_id if link_id.startswith("link:") else f"link:{link_id}"
            graph.add_node(
                EvidenceNode(
                    id=node_id,
                    type=NodeType.LINK,
                    link_id=link_id,
                    endpoint_a=endpoint_a,
                    endpoint_b=endpoint_b,
                    length_km=link.get("length_km"),
                    loss_db=link.get("loss_db"),
                    confidence=1.0,
                    inferred=False,
                )
            )
            if endpoint_a in port_nodes:
                graph.add_edge(
                    EvidenceEdge(
                        source=port_nodes[endpoint_a],
                        target=node_id,
                        type=EdgeType.TOPOLOGY,
                        confidence=1.0,
                        inferred=False,
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
                        inferred=False,
                        distance_km=link.get("length_km"),
                    )
                )

    def _infer_missing_links(
        self,
        topology: Dict[str, Any],
        graph: EvidenceGraph,
        port_nodes: Dict[str, str],
    ) -> None:
        """Infer internal links from unconnected out/in port pairs on the same device.

        Inferred links and their TOPOLOGY edges are marked with ``confidence=0.6`` and
        ``inferred=true`` to distinguish them from authoritative CMDB topology.
        """
        explicit_ports: Set[str] = set()
        for link in topology.get("links", []):
            if link.get("endpoint_a"):
                explicit_ports.add(link["endpoint_a"])
            if link.get("endpoint_b"):
                explicit_ports.add(link["endpoint_b"])

        ports_by_device: Dict[str, List[Dict[str, Any]]] = {}
        for port in topology.get("ports", []):
            ports_by_device.setdefault(port.get("device_id", ""), []).append(port)

        for device_id, ports in ports_by_device.items():
            if not device_id:
                continue

            # Only infer when the device has unconnected out/in port pairs.
            unconnected = [p for p in ports if p["port_id"] not in explicit_ports]
            out_ports = [p for p in unconnected if str(p.get("direction", "")).lower() == "out"]
            in_ports = [p for p in unconnected if str(p.get("direction", "")).lower() == "in"]
            if not out_ports or not in_ports:
                continue

            out_port = out_ports[0]
            in_port = in_ports[0]
            out_id = out_port["port_id"]
            in_id = in_port["port_id"]
            link_id = f"inferred-{device_id}-{out_id}-{in_id}"
            node_id = f"link:{link_id}"

            try:
                graph.add_node(
                    EvidenceNode(
                        id=node_id,
                        type=NodeType.LINK,
                        link_id=link_id,
                        endpoint_a=out_id,
                        endpoint_b=in_id,
                        confidence=0.6,
                        inferred=True,
                    )
                )
            except ValueError:
                # Inferred link already exists; skip.
                continue

            graph.add_edge(
                EvidenceEdge(
                    source=port_nodes[out_id],
                    target=node_id,
                    type=EdgeType.TOPOLOGY,
                    confidence=0.6,
                    inferred=True,
                )
            )
            graph.add_edge(
                EvidenceEdge(
                    source=port_nodes[in_id],
                    target=node_id,
                    type=EdgeType.TOPOLOGY,
                    confidence=0.6,
                    inferred=True,
                )
            )

    def _mark_isolated_nodes(self, graph: EvidenceGraph) -> None:
        """Mark Device/Port/Link nodes that do not participate in any TOPOLOGY edge."""
        data = graph._read()
        nodes = {n["id"]: n for n in data.get("nodes", [])}
        topo_participants: Set[str] = set()
        for edge in data.get("edges", []):
            if edge.get("type") == EdgeType.TOPOLOGY.value:
                topo_participants.add(edge["source"])
                topo_participants.add(edge["target"])

        for node in nodes.values():
            if node.get("type") in {NodeType.DEVICE.value, NodeType.PORT.value, NodeType.LINK.value}:
                node["isolated"] = node["id"] not in topo_participants
        graph._write(data)

    def _build_alarms(self, fact_table: Dict[str, Any], graph: EvidenceGraph) -> None:
        alarms: List[Dict[str, Any]] = fact_table.get("alarms", [])
        device_ids = {n.properties.get("device_id") for n in graph.get_nodes(NodeType.DEVICE)}
        for alarm in alarms:
            alarm_id = alarm.get("alarm_id")
            node_id = alarm_id if alarm_id.startswith("alm:") else f"alm:{alarm_id}"
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
                target = port_id if port_id.startswith("port:") else f"port:{port_id}"
            elif device_id and device_id in device_ids:
                target = device_id if device_id.startswith("dev:") else f"dev:{device_id}"

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
