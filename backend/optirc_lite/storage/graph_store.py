import json
from pathlib import Path
from typing import Any, Dict, List

from optirc_lite.config import settings


class LiteGraphStore:
    """Small JSON graph store for topology-aware reasoning."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.graph_path

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps({"nodes": [], "edges": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def neighbors(self, node_ids: List[str], depth: int = 1) -> Dict[str, Any]:
        graph = json.loads(self.path.read_text(encoding="utf-8"))
        nodes = {node.get("id"): node for node in graph.get("nodes", [])}
        edges = graph.get("edges", [])
        frontier = set(node_ids)
        visited = set(node_ids)
        matched_edges = []

        for _ in range(depth):
            next_frontier = set()
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")
                if source in frontier or target in frontier:
                    matched_edges.append(edge)
                    if source and source not in visited:
                        next_frontier.add(source)
                    if target and target not in visited:
                        next_frontier.add(target)
            visited |= next_frontier
            frontier = next_frontier

        return {
            "nodes": [nodes[node_id] for node_id in visited if node_id in nodes],
            "edges": matched_edges,
        }

    def add_case(self, session_id: str, root_cause: str, device_ids: List[str]) -> None:
        graph = json.loads(self.path.read_text(encoding="utf-8"))
        nodes = graph.setdefault("nodes", [])
        edges = graph.setdefault("edges", [])
        case_id = f"case:{session_id}"
        if not any(node.get("id") == case_id for node in nodes):
            nodes.append({"id": case_id, "type": "case", "label": root_cause})
        existing = {(edge.get("source"), edge.get("target"), edge.get("type")) for edge in edges}
        for device_id in device_ids:
            if not any(node.get("id") == device_id for node in nodes):
                nodes.append({"id": device_id, "type": "device", "label": device_id})
            key = (case_id, device_id, "AFFECTS")
            if key not in existing:
                edges.append({"source": case_id, "target": device_id, "type": "AFFECTS"})
        self.path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


graph_store = LiteGraphStore()
