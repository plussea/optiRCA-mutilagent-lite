import asyncio
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from optirc_lite.config import settings
from optirc_lite.runtime.agent_runtime import AgentRuntime
from optirc_lite.skills.builtin import create_builtin_skills
from optirc_lite.storage.evidence_graph import EvidenceGraph, evidence_graph
from optirc_lite.storage.graph_store import graph_store
from optirc_lite.storage.sqlite_store import store
from optirc_lite.storage.vector_store import vector_store
from optirc_lite.tools.builtin import create_builtin_tools
from optirc_lite.workflow.graph import build_workflow
from optirc_lite.workflow.state import AgentState


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    store.init()
    vector_store.init()
    graph_store.init()
    evidence_graph.init()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workflow = build_workflow()
closure_runtime = AgentRuntime(skills=create_builtin_skills(), tools=create_builtin_tools())
refactor_runtime = AgentRuntime(skills=create_builtin_skills(), tools=create_builtin_tools())


def _initial_state(session_id: str, raw_input: Path) -> AgentState:
    return {
        "session_id": session_id,
        "raw_input": str(raw_input),
        "status": "init",
        "pending_human": False,
        "human_decision": None,
        "retry_count": 0,
        "perception": {},
        "diagnosis": {},
        "validation": {},
        "planning": {},
        "solution_validation": {},
        "human_review": {},
        "closure": {},
        "runtime_context": {},
        "observations": [],
        "tool_calls": [],
        "decision_trace": [],
        "error_message": None,
    }


def _submit_workflow(session_id: str, initial_state: AgentState, source_name: str) -> None:
    store.upsert_session(session_id, "init", initial_state)
    store.add_event(session_id, "workflow.submitted", {"filename": source_name})

    async def run_pipeline() -> None:
        try:
            final_state = await workflow.ainvoke(initial_state)
            store.upsert_session(session_id, final_state.get("status", "unknown"), dict(final_state))
            store.add_event(session_id, "workflow.completed", dict(final_state))
        except Exception as exc:
            error_state = {**initial_state, "status": "error", "error_message": str(exc)}
            store.upsert_session(session_id, "error", error_state)
            store.add_event(session_id, "workflow.error", {"error": str(exc)})

    asyncio.create_task(run_pipeline())


def _degraded_parse_response(reason: str, exc: Exception | None = None) -> Dict[str, Any]:
    return {
        "status": "degraded",
        "root_cause": {},
        "evidence_chain": [],
        "confidence": 0.0,
        "dossier_id": None,
        "suggestion": "解析或拓扑构建失败，请人工复核告警与拓扑数据。",
        "requires_human_review": True,
        "degradation_reason": reason,
        "error": str(exc) if exc else None,
    }


@app.post("/v1/refactor/parse")
async def refactor_parse(
    alarms: UploadFile = File(...),
    topology: str = Form(...),
) -> Dict[str, Any]:
    if not alarms.filename or not alarms.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 告警文件")

    try:
        topology_data = json.loads(topology)
    except json.JSONDecodeError as exc:
        return _degraded_parse_response("invalid_topology", exc)

    session_id = str(uuid.uuid4())
    target = settings.upload_dir / f"{session_id}_{Path(alarms.filename).name}"
    with target.open("wb") as handle:
        shutil.copyfileobj(alarms.file, handle)

    state: AgentState = {
        "session_id": session_id,
        "raw_input": str(target),
        "topology": topology_data,
        "status": "init",
        "pending_human": False,
        "human_decision": None,
        "retry_count": 0,
        "perception": {},
        "diagnosis": {},
        "validation": {},
        "planning": {},
        "solution_validation": {},
        "human_review": {},
        "closure": {},
        "runtime_context": {},
        "observations": [],
        "tool_calls": [],
        "decision_trace": [],
        "error_message": None,
    }

    try:
        perception_update = await refactor_runtime.run_phase("perception", state)
        state.update(perception_update)
        if "perception" not in state or not state["perception"]:
            return _degraded_parse_response("perception_failure")

        topology_update = await refactor_runtime.run_phase("topology", state)
        state.update(topology_update)
        if "topology" not in state or not state["topology"]:
            return _degraded_parse_response("topology_failure")
    except Exception as exc:
        return _degraded_parse_response("agent_failure", exc)

    return {
        "status": "perceived",
        "session_id": session_id,
        "fact_table": state["perception"],
        "evidence_graph": EvidenceGraph()._read(),
    }


@app.post("/v1/sessions")
async def create_session(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="当前 Lite 版本仅支持 CSV 文件")

    session_id = str(uuid.uuid4())
    target = settings.upload_dir / f"{session_id}_{Path(file.filename).name}"
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    _submit_workflow(session_id, _initial_state(session_id, target), file.filename)
    return {"session_id": session_id, "status": "init"}


@app.post("/v1/demo-session")
async def create_demo_session() -> Dict[str, Any]:
    demo_source = Path(__file__).resolve().parents[3] / "examples" / "true_example.csv"
    if not demo_source.exists():
        raise HTTPException(status_code=404, detail="examples/true_example.csv not found")

    session_id = str(uuid.uuid4())
    target = settings.upload_dir / f"{session_id}_true_example.csv"
    shutil.copyfile(demo_source, target)

    _submit_workflow(session_id, _initial_state(session_id, target), "true_example.csv")
    return {"session_id": session_id, "status": "init", "demo": "true_example.csv"}


@app.get("/v1/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    state = store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return state


@app.get("/v1/sessions/{session_id}/events")
async def get_events(session_id: str) -> Dict[str, Any]:
    return {"session_id": session_id, "events": store.list_events(session_id)}


@app.post("/v1/sessions/{session_id}/human-decision")
async def submit_human_decision(
    session_id: str,
    decision: str = Form(...),
    notes: str = Form(""),
) -> Dict[str, Any]:
    if decision not in {"approved", "rejected", "escalated"}:
        raise HTTPException(status_code=400, detail="decision must be approved/rejected/escalated")

    state = store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    if not state.get("pending_human"):
        raise HTTPException(status_code=409, detail="session is not waiting for human review")

    state["pending_human"] = False
    state["human_decision"] = decision
    state["human_review"] = {
        **state.get("human_review", {}),
        "decision": decision,
        "notes": notes,
    }
    store.add_event(session_id, "human.decision", {"decision": decision, "notes": notes})

    if decision == "approved":
        store.add_event(session_id, "closure.start", {"input": state.get("human_review", {})})
        store.upsert_session(session_id, "closure_running", {**state, "status": "closure_running"})
        closure_update = await closure_runtime.run_phase("closure", state)
        state.update(closure_update)
        state["status"] = "closed"
        store.add_event(session_id, "closure.end", {"status": "closed", "output": state.get("closure", {})})
    elif decision == "rejected":
        state["status"] = "rejected"
    else:
        state["status"] = "escalated"

    store.upsert_session(session_id, state["status"], state)
    return {"session_id": session_id, "status": state["status"], "human_decision": decision}


@app.get("/v1/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "storage": "sqlite+lancedb+json-graph",
        "workflow": "langgraph",
        "skills": list(create_builtin_skills()._skills.keys()),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("optirc_lite.api.main:app", host=settings.host, port=settings.port, reload=True)
