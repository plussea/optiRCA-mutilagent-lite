"""Heterogeneous evidence graph — shared blackboard for the multi-Agent diagnosis system."""

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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


evidence_graph = EvidenceGraph()
