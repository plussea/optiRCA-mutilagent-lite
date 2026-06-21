import csv
from pathlib import Path
from typing import Any, Dict, List

from optirc_lite.storage.graph_store import graph_store
from optirc_lite.storage.vector_store import vector_store
from optirc_lite.tools.llm import llm_tool
from optirc_lite.tools.registry import ToolRegistry


async def parse_csv(path: str) -> Dict[str, Any]:
    rows: List[Dict[str, str]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(dict(row))
    headers = list(rows[0].keys()) if rows else []
    return {"rows": rows, "headers": headers}


async def vector_search(query: str, top_k: int = 5, doc_type: str | None = None) -> List[Dict[str, Any]]:
    return vector_store.search(query=query, top_k=top_k, doc_type=doc_type)


async def graph_neighbors(node_ids: List[str], depth: int = 1) -> Dict[str, Any]:
    return graph_store.neighbors(node_ids=node_ids, depth=depth)


async def save_case_knowledge(session_id: str, root_cause: str, device_ids: List[str]) -> Dict[str, Any]:
    content = f"案例 {session_id}: 根因={root_cause}; 影响设备={', '.join(device_ids) or 'unknown'}"
    vector_store.add(content, {"type": "case", "session_id": session_id})
    graph_store.add_case(session_id=session_id, root_cause=root_cause, device_ids=device_ids)
    return {"stored": True, "content": content}


async def llm_generate_json(system: str, user: str, temperature: float = 0.2) -> Dict[str, Any]:
    return await llm_tool.generate_json(system=system, user=user, temperature=temperature)


async def llm_generate_text(system: str, user: str, temperature: float = 0.2) -> str:
    return await llm_tool.generate_text(system=system, user=user, temperature=temperature)


def create_builtin_tools() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("csv.parse", parse_csv)
    registry.register("vector.search", vector_search)
    registry.register("graph.neighbors", graph_neighbors)
    registry.register("knowledge.save_case", save_case_knowledge)
    registry.register("llm.generate_json", llm_generate_json)
    registry.register("llm.generate_text", llm_generate_text)
    return registry
