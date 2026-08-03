"""Heterogeneous evidence graph — shared blackboard for the multi-Agent diagnosis system."""

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field, model_validator

from optirc_lite.config import settings


class NodeType(str, Enum):
    DEVICE = "Device"
    PORT = "Port"
    LINK = "Link"
    ALARM = "Alarm"
    SERVICE = "Service"


class EdgeType(str, Enum):
    BELONGS_TO = "BELONGS_TO"
    TOPOLOGY = "TOPOLOGY"
    PROPAGATES = "PROPAGATES"
    CARRIES = "CARRIES"


class EvidenceNode(BaseModel):
    id: str
    type: NodeType
    # Flexible domain properties beyond the common ones
    properties: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        # Extract known fields; everything else goes into properties.
        known = {"id", "type", "properties"}
        properties = data.pop("properties", {}) or {}
        for key in list(data.keys()):
            if key not in known:
                properties[key] = data.pop(key)
        super().__init__(properties=properties, **data)

    # Required-ish fields per type, stored in properties for forward compatibility
    @model_validator(mode="after")
    def ensure_type_fields(self):
        props = self.properties
        if self.type == NodeType.DEVICE and "device_id" not in props:
            props.setdefault("device_id", self.id)
        if self.type == NodeType.PORT and "port_id" not in props:
            props.setdefault("port_id", self.id)
        if self.type == NodeType.LINK and "link_id" not in props:
            props.setdefault("link_id", self.id)
        if self.type == NodeType.ALARM and "alarm_id" not in props:
            props.setdefault("alarm_id", self.id)
        if self.type == NodeType.SERVICE and "service_id" not in props:
            props.setdefault("service_id", self.id)
        return self

    def model_dump(self, **kwargs):
        return {"id": self.id, "type": self.type.value, **self.properties}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceNode":
        node_id = data.pop("id")
        node_type = NodeType(data.pop("type"))
        return cls(id=node_id, type=node_type, properties=data)


class EvidenceEdge(BaseModel):
    source: str
    target: str
    type: EdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        # Extract known fields; everything else goes into properties.
        known = {"source", "target", "type", "properties"}
        properties = data.pop("properties", {}) or {}
        for key in list(data.keys()):
            if key not in known:
                properties[key] = data.pop(key)
        super().__init__(properties=properties, **data)

    def model_dump(self, **kwargs):
        return {"source": self.source, "target": self.target, "type": self.type.value, **self.properties}

    def __getattr__(self, name: str):
        # Allow convenient property access like edge.confidence
        if name in self.properties:
            return self.properties[name]
        raise AttributeError(f"'EvidenceEdge' object has no attribute '{name}'")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceEdge":
        source = data.pop("source")
        target = data.pop("target")
        edge_type = EdgeType(data.pop("type"))
        return cls(source=source, target=target, type=edge_type, properties=data)


class EvidenceSubgraph(BaseModel):
    nodes: List[EvidenceNode]
    edges: List[EvidenceEdge]


class EvidenceGraph:
    """JSON-backed heterogeneous evidence graph.

    This is the shared blackboard. All Agents read and write this graph
    instead of calling each other directly.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.evidence_graph_path

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps({"nodes": [], "edges": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _validate_edge(self, edge: EvidenceEdge, node_index: Dict[str, EvidenceNode]) -> None:
        if edge.type == EdgeType.PROPAGATES:
            source = node_index.get(edge.source)
            if source is None:
                raise ValueError(f"PROPAGATES edge source '{edge.source}' does not exist")
            if source.type == NodeType.DEVICE:
                raise ValueError("PROPAGATES edges cannot originate from DEVICE")

    def add_node(self, node: EvidenceNode) -> None:
        data = self._read()
        nodes = data.setdefault("nodes", [])
        if any(n["id"] == node.id for n in nodes):
            raise ValueError(f"Node with id '{node.id}' already exists")
        nodes.append(node.model_dump())
        self._write(data)

    def add_edge(self, edge: EvidenceEdge) -> None:
        data = self._read()
        node_index = {
            n["id"]: EvidenceNode.from_dict({**n}) for n in data.get("nodes", [])
        }
        if edge.source not in node_index:
            raise ValueError(f"Edge source '{edge.source}' does not exist")
        if edge.target not in node_index:
            raise ValueError(f"Edge target '{edge.target}' does not exist")
        self._validate_edge(edge, node_index)
        edges = data.setdefault("edges", [])
        edges.append(edge.model_dump())
        self._write(data)

    def get_nodes(self, node_type: Optional[NodeType] = None) -> List[EvidenceNode]:
        data = self._read()
        nodes = [EvidenceNode.from_dict({**n}) for n in data.get("nodes", [])]
        if node_type:
            nodes = [n for n in nodes if n.type == node_type]
        return nodes

    def get_edges(self, edge_type: Optional[EdgeType] = None) -> List[EvidenceEdge]:
        data = self._read()
        edges = [EvidenceEdge.from_dict({**e}) for e in data.get("edges", [])]
        if edge_type:
            edges = [e for e in edges if e.type == edge_type]
        return edges

    def neighbors(
        self,
        node_ids: List[str],
        depth: int = 1,
        edge_types: Optional[Set[EdgeType]] = None,
    ) -> EvidenceSubgraph:
        data = self._read()
        node_index = {n["id"]: n for n in data.get("nodes", [])}
        edges = [EvidenceEdge.from_dict({**e}) for e in data.get("edges", [])]
        if edge_types:
            edges = [e for e in edges if e.type in edge_types]

        frontier = set(node_ids)
        visited = set(node_ids)
        matched_edges: List[EvidenceEdge] = []
        seen_edges: Set[tuple] = set()

        for _ in range(depth):
            next_frontier: Set[str] = set()
            for edge in edges:
                if edge.source in frontier or edge.target in frontier:
                    edge_key = (edge.source, edge.target, edge.type.value, tuple(sorted(edge.properties.items())))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        matched_edges.append(edge)
                    if edge.source not in visited:
                        next_frontier.add(edge.source)
                    if edge.target not in visited:
                        next_frontier.add(edge.target)
            visited |= next_frontier
            frontier = next_frontier

        return EvidenceSubgraph(
            nodes=[EvidenceNode.from_dict({**node_index[nid]}) for nid in visited if nid in node_index],
            edges=matched_edges,
        )

    def get_node(self, node_id: str) -> Optional[EvidenceNode]:
        data = self._read()
        for n in data.get("nodes", []):
            if n["id"] == node_id:
                return EvidenceNode.from_dict({**n})
        return None

    @staticmethod
    def parse_node_id(node_id: str) -> Tuple[Optional[NodeType], str]:
        """Parse a node id like dev:olt-a into (NodeType, local_id)."""
        if ":" not in node_id:
            return None, node_id
        prefix, local_id = node_id.split(":", 1)
        mapping = {
            "dev": NodeType.DEVICE,
            "port": NodeType.PORT,
            "link": NodeType.LINK,
            "alm": NodeType.ALARM,
            "svc": NodeType.SERVICE,
        }
        return mapping.get(prefix), local_id

    def get_alarms_for_node(self, node_id: str) -> List[EvidenceNode]:
        """Return all ALARM nodes that belong to this node or its descendants.

        For a device, includes alarms on the device itself and on its ports.
        For a port, includes alarms on the port itself.
        For a link, includes alarms on both endpoint ports/devices.
        """
        node_type, _ = self.parse_node_id(node_id)
        if node_type is None:
            return []

        data = self._read()
        nodes = {n["id"]: EvidenceNode.from_dict({**n}) for n in data.get("nodes", [])}
        edges = [EvidenceEdge.from_dict({**e}) for e in data.get("edges", [])]

        belongs = {e.source: e.target for e in edges if e.type == EdgeType.BELONGS_TO}
        topo = [e for e in edges if e.type == EdgeType.TOPOLOGY]

        covered: Set[str] = set()

        if node_type == NodeType.DEVICE:
            covered.add(node_id)
            _, local_id = self.parse_node_id(node_id)
            # Topology-linked ports
            for edge in topo:
                if edge.source == node_id:
                    covered.add(edge.target)
                elif edge.target == node_id:
                    covered.add(edge.source)
            # Ports that declare this device as their parent even without a topology edge
            for node in nodes.values():
                if node.type == NodeType.PORT and node.properties.get("device_id") == local_id:
                    covered.add(node.id)

        elif node_type == NodeType.PORT:
            covered.add(node_id)
            # Include topology-linked neighbors (parent device, attached link)
            for edge in topo:
                if edge.source == node_id:
                    covered.add(edge.target)
                elif edge.target == node_id:
                    covered.add(edge.source)

        elif node_type == NodeType.LINK:
            link_node = nodes.get(node_id)
            if link_node:
                endpoints = {
                    link_node.properties.get("endpoint_a"),
                    link_node.properties.get("endpoint_b"),
                }
                for endpoint in endpoints:
                    if not endpoint:
                        continue
                    port_id = f"port:{endpoint}"
                    covered.add(port_id)
                    for edge in topo:
                        if edge.source == port_id:
                            covered.add(edge.target)
                        elif edge.target == port_id:
                            covered.add(edge.source)

        alarm_ids = {alarm_id for alarm_id, target in belongs.items() if target in covered}
        return [nodes[alarm_id] for alarm_id in alarm_ids if alarm_id in nodes]

    def get_neighbors_by_type(
        self,
        node_id: str,
        edge_type: EdgeType,
        direction: str = "both",
    ) -> EvidenceSubgraph:
        """Return neighbors reachable via edges of the given type."""
        data = self._read()
        node_index = {n["id"]: n for n in data.get("nodes", [])}
        edges = [
            EvidenceEdge.from_dict({**e})
            for e in data.get("edges", [])
            if e.get("type") == edge_type.value
        ]

        matched: List[EvidenceEdge] = []
        visited: Set[str] = {node_id}
        for edge in edges:
            if direction in {"out", "both"} and edge.source == node_id:
                matched.append(edge)
                visited.add(edge.target)
            if direction in {"in", "both"} and edge.target == node_id:
                matched.append(edge)
                visited.add(edge.source)

        return EvidenceSubgraph(
            nodes=[EvidenceNode.from_dict({**node_index[nid]}) for nid in visited if nid in node_index],
            edges=matched,
        )

    def get_link_endpoint_alarms(self, link_id: str) -> Tuple[Set[str], Set[str]]:
        """Return alarm IDs on each endpoint of a link.

        Returns (endpoint_a_alarms, endpoint_b_alarms).
        """
        link = self.get_node(link_id)
        if link is None or link.type != NodeType.LINK:
            return set(), set()

        endpoint_a = link.properties.get("endpoint_a")
        endpoint_b = link.properties.get("endpoint_b")

        alarms_a: Set[str] = set()
        alarms_b: Set[str] = set()

        if endpoint_a:
            alarms_a = {a.id for a in self.get_alarms_for_node(f"port:{endpoint_a}")}
        if endpoint_b:
            alarms_b = {a.id for a in self.get_alarms_for_node(f"port:{endpoint_b}")}

        return alarms_a, alarms_b

    def alarm_clusters(self) -> List[Set[str]]:
        """Group alarms into connected clusters based on topology proximity.

        Two alarms are in the same cluster when their attachment points (the
        device/port they BELONG_TO) are the same or connected by TOPOLOGY edges.
        Multi-cluster results suggest a possible multi-root-cause scenario.
        """
        data = self._read()
        edges = [EvidenceEdge.from_dict({**e}) for e in data.get("edges", [])]

        belongs = {e.source: e.target for e in edges if e.type == EdgeType.BELONGS_TO}
        topo = [e for e in edges if e.type == EdgeType.TOPOLOGY]

        # Build topology adjacency between attachment points.
        topo_adj: Dict[str, Set[str]] = {}
        for edge in topo:
            topo_adj.setdefault(edge.source, set()).add(edge.target)
            topo_adj.setdefault(edge.target, set()).add(edge.source)

        # Union-find over anchors that actually carry alarms.
        anchors: Set[str] = set(belongs.values())
        parent = {anchor: anchor for anchor in anchors}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for anchor in list(anchors):
            for neighbor in topo_adj.get(anchor, set()):
                if neighbor in anchors:
                    union(anchor, neighbor)

        clusters: Dict[str, Set[str]] = {}
        for alarm_id, anchor in belongs.items():
            root = find(anchor)
            clusters.setdefault(root, set()).add(alarm_id)

        return list(clusters.values())

    def get_alarm_clusters_for_node(self, node_id: str) -> Set[str]:
        """Return the alarm cluster ids (anchor root ids) a candidate node covers.

        A node covers a cluster if it can explain at least one alarm in that
        cluster through topology proximity.
        """
        clusters = self.alarm_clusters()
        covered_alarms = {a.id for a in self.get_alarms_for_node(node_id)}
        covered_clusters: Set[str] = set()
        for cluster in clusters:
            if cluster & covered_alarms:
                covered_clusters.add(id(cluster))
        return covered_clusters

    def build_propagates_edges(self) -> None:
        """Create PROPAGATES edges from Port/Link nodes to their reachable Alarms."""
        data = self._read()
        nodes = {n["id"]: EvidenceNode.from_dict({**n}) for n in data.get("nodes", [])}
        edges = [EvidenceEdge.from_dict({**e}) for e in data.get("edges", [])]

        belongs = {e.source: e.target for e in edges if e.type == EdgeType.BELONGS_TO}
        topo = [e for e in edges if e.type == EdgeType.TOPOLOGY]

        # port -> device
        port_to_device: Dict[str, str] = {}
        for edge in topo:
            if edge.source.startswith("port:") and edge.target.startswith("dev:"):
                port_to_device[edge.source] = edge.target
            elif edge.source.startswith("dev:") and edge.target.startswith("port:"):
                port_to_device[edge.target] = edge.source

        # link -> ports
        link_to_ports: Dict[str, Set[str]] = {}
        for link in nodes.values():
            if link.type != NodeType.LINK:
                continue
            ports_set: Set[str] = set()
            for endpoint in (link.properties.get("endpoint_a"), link.properties.get("endpoint_b")):
                if endpoint:
                    ports_set.add(f"port:{endpoint}")
            link_to_ports[link.id] = ports_set

        existing = {(e.source, e.target) for e in edges if e.type == EdgeType.PROPAGATES}

        def alarms_for_target(target: str) -> Set[str]:
            result: Set[str] = set()
            for alarm_id, belongs_to in belongs.items():
                if belongs_to == target:
                    result.add(alarm_id)
                elif belongs_to == port_to_device.get(target):
                    result.add(alarm_id)
            return result

        new_edges: List[Dict[str, Any]] = []

        for port_id in nodes:
            if not port_id.startswith("port:"):
                continue
            for alarm_id in alarms_for_target(port_id):
                key = (port_id, alarm_id)
                if key in existing:
                    continue
                existing.add(key)
                new_edges.append(
                    EvidenceEdge(source=port_id, target=alarm_id, type=EdgeType.PROPAGATES, confidence=1.0).model_dump()
                )

        for link_id, ports in link_to_ports.items():
            for port_id in ports:
                for alarm_id in alarms_for_target(port_id):
                    key = (link_id, alarm_id)
                    if key in existing:
                        continue
                    existing.add(key)
                    new_edges.append(
                        EvidenceEdge(source=link_id, target=alarm_id, type=EdgeType.PROPAGATES, confidence=1.0).model_dump()
                    )

        data.setdefault("edges", []).extend(new_edges)
        self._write(data)


# Module-level singleton for callers that don't manage their own graph path.
evidence_graph = EvidenceGraph()

