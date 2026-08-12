import asyncio
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from optirc_lite.config import settings
from optirc_lite.preflight import (
    PreflightRecord,
    prepare_topology,
    preflight_repository,
    sample_summary,
)
from optirc_lite.runtime.agent_runtime import AgentRuntime
from optirc_lite.skills.archivist import archivist
from optirc_lite.skills.builtin import create_builtin_skills
from optirc_lite.skills.evaluator import evaluator
from optirc_lite.skills.gepa import gepa
from optirc_lite.storage.evidence_graph import EvidenceGraph, evidence_graph, use_evidence_graph
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
diagnosis_tasks: dict[str, asyncio.Task[None]] = {}


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
        "evidence_graph": {"nodes": [], "edges": []},
        "candidates": [],
        "critic": {},
        "max_fallback_rounds": 2,
        "fallback_round": 0,
        "degradation_reason": None,
        "response": {},
        "dossier_id": None,
        "input": {},
    }


def _submit_workflow(session_id: str, state: AgentState, filename: str) -> None:
    import asyncio

    async def _run() -> None:
        final_state = await workflow.ainvoke(state)
        store.upsert_session(
            session_id,
            final_state.get("status", "unknown"),
            final_state,
        )

    asyncio.create_task(_run())


def _degraded_parse_response(
    reason: str,
    input_payload: Dict[str, Any],
    exc: Exception | None = None,
) -> Dict[str, Any]:
    return {
        "status": "degraded",
        "session_id": None,
        "fact_table": {},
        "evidence_graph": {"nodes": [], "edges": []},
        "root_cause": {},
        "evidence_chain": [],
        "confidence": 0.0,
        "dossier_id": None,
        "suggestion": "解析或拓扑构建失败，请人工复核告警与拓扑数据。",
        "requires_human_review": True,
        "degradation_reason": reason,
        "error": str(exc) if exc else None,
    }


def _degraded_diagnose_response(
    reason: str,
    input_payload: Dict[str, Any],
    evidence_graph: Dict[str, Any] | None = None,
    dossier_id: str | None = None,
    session_id: str | None = None,
    exc: Exception | None = None,
) -> Dict[str, Any]:
    return {
        "status": "degraded",
        "dossier_id": dossier_id,
        "session_id": session_id,
        "root_cause": {},
        "evidence_chain": [],
        "confidence": 0.0,
        "suggestion": "自动推理降级，请人工复核拓扑与告警时间线。",
        "requires_human_review": True,
        "degradation_reason": reason,
        "input": input_payload,
        "evidence_graph": evidence_graph or {"nodes": [], "edges": []},
        "critic_verdict": None,
        "error": str(exc) if exc else None,
    }


class JudgeRankRequest(BaseModel):
    fact_table: Dict[str, Any]
    evidence_graph: Dict[str, Any]


class CriticRequest(BaseModel):
    candidates: List[Dict[str, Any]]
    evidence_graph: Dict[str, Any]
    max_fallback_rounds: int = 0


class CreateDiagnosisRequest(BaseModel):
    preflight_id: str
    max_fallback_rounds: int = 2


class DiagnosisReviewRequest(BaseModel):
    decision: str
    ground_truth: Dict[str, Any] | None = None
    notes: str = ""


def _degraded_critic_response(reason: str, exc: Exception | None = None) -> Dict[str, Any]:
    return {
        "status": "degraded",
        "verdict": "reject",
        "reasons": ["Critic/Orchestrator 无法收敛"],
        "fallback_action": None,
        "confidence": 0.0,
        "suggestion": "达到最大回退次数仍未通过复核，请人工复核候选根因。",
        "requires_human_review": True,
        "degradation_reason": reason,
        "error": str(exc) if exc else None,
    }


def _degraded_judge_response(reason: str, exc: Exception | None = None) -> Dict[str, Any]:
    return {
        "status": "degraded",
        "candidates": [],
        "confidence": 0.0,
        "suggestion": "Judge/Ranker 失败或证据不足，请人工复核证据图。",
        "requires_human_review": True,
        "degradation_reason": reason,
        "error": str(exc) if exc else None,
    }


@app.post("/api/v1/preflight")
async def preflight_diagnosis_sample(
    alarms: UploadFile = File(...),
    topology: str | None = Form(None),
    topology_file: UploadFile | None = File(None),
) -> Dict[str, Any]:
    if not alarms.filename or not alarms.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="告警文件必须是 CSV。")

    topology_data: Dict[str, Any] | None = None
    topology_text = topology
    if topology_file is not None:
        topology_text = (await topology_file.read()).decode("utf-8-sig")
    if topology_text:
        try:
            topology_data = json.loads(topology_text)
        except json.JSONDecodeError as exc:
            return {
                "status": "input_not_ready",
                "preflight_id": f"PF-{str(uuid.uuid4())[:8].upper()}",
                "sample_summary": {},
                "topology": {"source": "provided", "confidence": 0.0, "devices": [], "ports": [], "links": []},
                "issues": [{"code": "TOPOLOGY_INVALID", "message": "拓扑 JSON 无法解析。", "detail": str(exc)}],
            }

    preflight_id = f"PF-{str(uuid.uuid4())[:8].upper()}"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / f"{preflight_id}_{Path(alarms.filename).name}"
    with target.open("wb") as handle:
        shutil.copyfileobj(alarms.file, handle)

    perception_update = await refactor_runtime.run_phase(
        "perception", {"raw_input": str(target), "perception": {}}
    )
    fact_table = perception_update.get("perception", {})
    prepared_topology, issues = prepare_topology(fact_table, topology_data)
    status = "input_not_ready" if issues else "ready"
    record = PreflightRecord(
        preflight_id=preflight_id,
        alarm_path=str(target),
        filename=alarms.filename,
        fact_table=fact_table,
        topology=prepared_topology,
        status=status,
        issues=issues,
    )
    preflight_repository.save(record)
    return {
        "status": status,
        "preflight_id": preflight_id,
        "sample_summary": sample_summary(fact_table),
        "alarms": fact_table.get("alarms", []),
        "topology": prepared_topology or {
            "source": "inferred" if topology_data is None else "provided",
            "confidence": 0.0,
            "devices": [],
            "ports": [],
            "links": [],
            "inference_explanations": [],
        },
        "issues": issues,
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
        return _degraded_parse_response("agent_failure", {"filename": alarms.filename}, exc)

    session_id = str(uuid.uuid4())
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / f"{session_id}_{Path(alarms.filename).name}"
    with target.open("wb") as handle:
        shutil.copyfileobj(alarms.file, handle)

    state: AgentState = _initial_state(session_id, target)
    state["topology"] = topology_data

    try:
        perception_update = await refactor_runtime.run_phase("perception", state)
        state.update(perception_update)
        if "perception" not in state or not state["perception"]:
            return _degraded_parse_response("perception_failure", {"filename": alarms.filename})

        topology_update = await refactor_runtime.run_phase("topology", state)
        state.update(topology_update)
        if "topology" not in state or not state["topology"]:
            return _degraded_parse_response("topology_failure", {"filename": alarms.filename})
    except Exception as exc:
        return _degraded_parse_response("agent_failure", {"filename": alarms.filename}, exc)

    return {
        "status": "perceived",
        "session_id": session_id,
        "fact_table": state["perception"],
        "evidence_graph": EvidenceGraph()._read(),
    }


@app.post("/v1/refactor/judge-rank")
async def refactor_judge_rank(request: JudgeRankRequest) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = EvidenceGraph()
    graph.init()
    graph._write(request.evidence_graph)

    if not request.evidence_graph.get("nodes") or request.fact_table.get("alarm_count", 0) == 0:
        return _degraded_judge_response("empty_evidence")

    state: AgentState = {
        "session_id": session_id,
        "raw_input": "",
        "perception": request.fact_table,
        "evidence_graph": request.evidence_graph,
        "status": "init",
        "pending_human": False,
        "human_decision": None,
        "retry_count": 0,
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
        "topology": {},
        "candidates": [],
        "critic": {},
        "max_fallback_rounds": 0,
        "fallback_round": 0,
        "degradation_reason": None,
        "response": {},
        "dossier_id": None,
        "input": {},
    }

    try:
        judge_update = await refactor_runtime.run_phase("judge", state)
        state.update(judge_update)
        if "judge" not in state or not state["judge"] or not state["judge"].get("candidates"):
            return _degraded_judge_response("judge_failure")

        rank_update = await refactor_runtime.run_phase("rank", state)
        state.update(rank_update)
        if "rank" not in state or not state["rank"]:
            return _degraded_judge_response("rank_failure")
    except Exception as exc:
        return _degraded_judge_response("agent_failure", exc)

    return {
        "status": "judged",
        "session_id": session_id,
        "candidates": state["rank"]["candidates"],
        "evidence_graph": request.evidence_graph,
    }


@app.post("/v1/refactor/critic")
async def refactor_critic(request: CriticRequest) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = EvidenceGraph()
    graph.init()
    graph._write(request.evidence_graph)

    alarm_count = len([n for n in request.evidence_graph.get("nodes", []) if n.get("type") == "Alarm"])
    state: AgentState = {
        "session_id": session_id,
        "raw_input": "",
        "perception": {"alarm_count": alarm_count},
        "evidence_graph": request.evidence_graph,
        "candidates": request.candidates,
        "status": "init",
        "pending_human": False,
        "human_decision": None,
        "retry_count": 0,
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
        "topology": {},
        "critic": {},
        "max_fallback_rounds": request.max_fallback_rounds,
        "fallback_round": 0,
        "degradation_reason": None,
        "response": {},
        "dossier_id": None,
        "input": {},
    }

    try:
        for round_idx in range(request.max_fallback_rounds + 1):
            critic_update = await refactor_runtime.run_phase("critic", state)
            state.update(critic_update)
            critic = state.get("critic", {})

            if critic.get("verdict") == "pass":
                return {
                    "status": "reviewed",
                    "session_id": session_id,
                    "verdict": "pass",
                    "reasons": critic.get("reasons", []),
                    "fallback_action": None,
                    "candidate": state["candidates"][0] if state["candidates"] else None,
                }

            if round_idx == request.max_fallback_rounds:
                if request.max_fallback_rounds > 0:
                    return _degraded_critic_response("max_fallback_exceeded")
                return {
                    "status": "reviewed",
                    "session_id": session_id,
                    "verdict": critic.get("verdict", "reject"),
                    "reasons": critic.get("reasons", []),
                    "fallback_action": critic.get("fallback_action"),
                    "candidate": state["candidates"][0] if state["candidates"] else None,
                }

            action = critic.get("fallback_action")
            if action == "FALLBACK_TO_JUDGE":
                judge_update = await refactor_runtime.run_phase("judge", state)
                state.update(judge_update)
                state["candidates"] = state["judge"].get("candidates", [])
                rank_update = await refactor_runtime.run_phase("rank", state)
                state.update(rank_update)
                state["candidates"] = state["rank"].get("candidates", [])
            elif action == "FALLBACK_TO_RANKER":
                state["judge"] = {"candidates": state["candidates"]}
                rank_update = await refactor_runtime.run_phase("rank", state)
                state.update(rank_update)
                state["candidates"] = state["rank"].get("candidates", [])
            else:
                return {
                    "status": "reviewed",
                    "session_id": session_id,
                    "verdict": critic.get("verdict", "reject"),
                    "reasons": critic.get("reasons", []),
                    "fallback_action": action,
                    "candidate": state["candidates"][0] if state["candidates"] else None,
                }
    except Exception as exc:
        return _degraded_critic_response("agent_failure", exc)

    return _degraded_critic_response("max_fallback_exceeded")


async def _run_diagnose_workflow(
    state: AgentState,
    dossier_id: str,
    input_payload: Dict[str, Any],
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Run the compiled LangGraph diagnosis workflow and return the dossier response."""
    wf = build_workflow()
    session_id = state.get("session_id", "unknown")
    session_graph = EvidenceGraph.for_session(session_id)
    session_graph.reset()

    with use_evidence_graph(session_graph.path):
        try:
            final_state = await asyncio.wait_for(wf.ainvoke(state), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            response = _degraded_diagnose_response(
                "critic_timeout", input_payload, session_graph._read(), dossier_id, session_id
            )
            _archive_from_response(dossier_id, state, response)
            return response
        except Exception as exc:
            response = _degraded_diagnose_response(
                "agent_failure", input_payload, session_graph._read(), dossier_id, session_id, exc
            )
            _archive_from_response(dossier_id, state, response)
            return response

        response = final_state.get("response")
        if response:
            _archive_from_response(dossier_id, final_state, response)
            return response

        response = _degraded_diagnose_response(
            "agent_failure", input_payload, session_graph._read(), dossier_id, session_id
        )
        _archive_from_response(dossier_id, state, response)
        return response


def _archive_from_response(
    dossier_id: str,
    state: AgentState,
    response: Dict[str, Any],
    human_decision: Optional[str] = None,
    human_notes: Optional[str] = None,
    ground_truth: Optional[Dict[str, Any]] = None,
) -> None:
    """Archive a dossier from a final API response and workflow state."""
    candidates = state.get("candidates", [])
    top = response.get("root_cause") or (candidates[0] if candidates else None)
    archivist.archive(
        dossier_id=dossier_id,
        session_id=state.get("session_id", "unknown"),
        input_payload=state.get("input", {}),
        evidence_graph=state.get("evidence_graph", {"nodes": [], "edges": []}),
        candidates=candidates,
        top_candidate=top,
        critic_verdict=response.get("critic_verdict"),
        degradation_reason=response.get("degradation_reason"),
        confidence=response.get("confidence", 0.0),
        requires_human_review=response.get("requires_human_review", True),
        human_decision=human_decision,
        human_notes=human_notes,
        ground_truth=ground_truth,
    )


@app.post("/api/v1/diagnose")
async def diagnose(
    alarms: UploadFile = File(...),
    topology: str = Form(...),
    max_fallback_rounds: int = Form(2),
) -> Dict[str, Any]:
    """End-to-end diagnosis: parse → topology → judge → rank → critic."""
    dossier_id = f"DOS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    if not alarms.filename or not alarms.filename.lower().endswith(".csv"):
        return _degraded_diagnose_response("agent_failure", {"filename": alarms.filename})

    try:
        topology_data = json.loads(topology)
    except json.JSONDecodeError as exc:
        return _degraded_diagnose_response("agent_failure", {"topology": topology}, exc=exc)

    session_id = str(uuid.uuid4())
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / f"{session_id}_{Path(alarms.filename).name}"
    with target.open("wb") as handle:
        shutil.copyfileobj(alarms.file, handle)

    input_payload = {
        "filename": alarms.filename,
        "topology": topology_data,
    }

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
        "evidence_graph": {"nodes": [], "edges": []},
        "candidates": [],
        "critic": {},
        "max_fallback_rounds": max_fallback_rounds,
        "fallback_round": 0,
        "degradation_reason": None,
        "response": {},
        "dossier_id": dossier_id,
        "input": input_payload,
    }

    return await _run_diagnose_workflow(state, dossier_id, input_payload)


async def _execute_async_diagnosis(state: AgentState) -> None:
    """Run one persisted diagnosis and publish a terminal event."""
    session_id = state["session_id"]
    dossier_id = state["dossier_id"]
    session_graph = EvidenceGraph.for_session(session_id)
    session_graph.reset()
    final_state: AgentState = state

    try:
        with use_evidence_graph(session_graph.path):
            final_state = await asyncio.wait_for(build_workflow().ainvoke(state), timeout=30.0)
        response = final_state.get("response") or _degraded_diagnose_response(
            "agent_failure",
            state.get("input", {}),
            session_graph._read(),
            dossier_id,
            session_id,
        )
        final_state = {**final_state, "status": response["status"], "response": response}
        _archive_from_response(dossier_id, final_state, response)
        terminal_type = (
            "diagnosis.completed" if response["status"] == "success" else "diagnosis.degraded"
        )
        store.add_event(
            session_id,
            terminal_type,
            {
                "type": terminal_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result": response,
            },
        )
        store.upsert_session(session_id, response["status"], final_state)
    except asyncio.CancelledError:
        persisted = store.get_session(session_id) or state
        cancelled_state = {
            **persisted,
            "status": "cancelled",
            "response": {},
            "dossier_id": None,
        }
        store.add_event(
            session_id,
            "diagnosis.cancelled",
            {
                "type": "diagnosis.cancelled",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        store.upsert_session(session_id, "cancelled", cancelled_state)
    except Exception as exc:
        response = _degraded_diagnose_response(
            "agent_failure",
            state.get("input", {}),
            session_graph._read(),
            dossier_id,
            session_id,
            exc,
        )
        final_state = {**final_state, "status": "degraded", "response": response}
        _archive_from_response(dossier_id, final_state, response)
        store.add_event(
            session_id,
            "diagnosis.degraded",
            {
                "type": "diagnosis.degraded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result": response,
            },
        )
        store.upsert_session(session_id, "degraded", final_state)
    finally:
        diagnosis_tasks.pop(session_id, None)


@app.post("/api/v1/diagnoses", status_code=202)
async def create_async_diagnosis(request: CreateDiagnosisRequest) -> Dict[str, Any]:
    record = preflight_repository.get(request.preflight_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PREFLIGHT_NOT_FOUND", "message": "输入预检不存在或已过期。"},
        )
    if record.status != "ready":
        raise HTTPException(
            status_code=409,
            detail={"code": "PREFLIGHT_NOT_READY", "message": "输入预检尚未通过，不能开始诊断。"},
        )
    if record.consumed_by:
        raise HTTPException(
            status_code=409,
            detail={"code": "PREFLIGHT_ALREADY_CONSUMED", "message": "该输入已创建诊断运行。"},
        )

    session_id = str(uuid.uuid4())
    claimed = preflight_repository.claim(request.preflight_id, session_id)
    if claimed is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "PREFLIGHT_ALREADY_CONSUMED", "message": "该输入已创建诊断运行。"},
        )

    dossier_id = f"DOS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    input_payload = {
        "filename": claimed.filename,
        "preflight_id": claimed.preflight_id,
        "topology": claimed.topology,
        "topology_source": claimed.topology.get("source", "provided"),
        "topology_confidence": claimed.topology.get("confidence", 1.0),
    }
    state = _initial_state(session_id, Path(claimed.alarm_path))
    state.update(
        {
            "status": "running",
            "topology": claimed.topology,
            "max_fallback_rounds": max(0, min(request.max_fallback_rounds, 5)),
            "dossier_id": dossier_id,
            "input": input_payload,
            "preflight_id": claimed.preflight_id,
        }
    )
    store.upsert_session(session_id, "running", state)
    store.add_event(
        session_id,
        "diagnosis.started",
        {
            "type": "diagnosis.started",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "preflight_id": claimed.preflight_id,
        },
    )
    task = asyncio.create_task(_execute_async_diagnosis(state))
    diagnosis_tasks[session_id] = task
    return {
        "session_id": session_id,
        "status": "running",
        "events_url": f"/api/v1/diagnoses/{session_id}/events",
    }


@app.get("/api/v1/diagnoses/{session_id}")
async def get_async_diagnosis(session_id: str) -> Dict[str, Any]:
    state = store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="diagnosis session not found")
    raw_status = state.get("status", "unknown")
    public_status = raw_status if raw_status in {"success", "degraded", "cancelled"} else "running"
    return {
        "session_id": session_id,
        "status": public_status,
        "preflight_id": state.get("preflight_id"),
        "dossier_id": state.get("dossier_id"),
        "result": state.get("response") or None,
        "input": state.get("input") or None,
        "review": state.get("human_review") or {"status": "unreviewed"},
        "events_url": f"/api/v1/diagnoses/{session_id}/events",
    }


@app.get("/api/v1/diagnoses/{session_id}/events")
async def stream_diagnosis_events(
    session_id: str,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="diagnosis session not found")
    try:
        cursor = max(0, int(last_event_id or "0"))
    except ValueError:
        cursor = 0

    async def event_stream():
        nonlocal cursor
        while True:
            events = store.list_events(session_id, after_id=cursor)
            for event in events:
                cursor = event["id"]
                data = json.dumps(event["payload"], ensure_ascii=False, separators=(",", ":"))
                yield f"id: {event['id']}\ndata: {data}\n\n"

            state = store.get_session(session_id) or {}
            if state.get("status") in {"success", "degraded", "cancelled"} and not store.list_events(
                session_id, after_id=cursor
            ):
                break
            await asyncio.sleep(0.08)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/v1/diagnoses/{session_id}/cancel", status_code=202)
async def cancel_async_diagnosis(session_id: str) -> Dict[str, Any]:
    state = store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="diagnosis session not found")
    if state.get("status") in {"success", "degraded", "cancelled"}:
        raise HTTPException(status_code=409, detail="diagnosis is already terminal")
    task = diagnosis_tasks.get(session_id)
    if task is None:
        raise HTTPException(status_code=409, detail="diagnosis task is not active")
    task.cancel()
    return {"session_id": session_id, "status": "cancelling"}


def _topology_root_ids(topology: Dict[str, Any]) -> set[str]:
    return {
        *(f"dev:{device['device_id']}" for device in topology.get("devices", []) if device.get("device_id")),
        *(f"port:{port['port_id']}" for port in topology.get("ports", []) if port.get("port_id")),
        *(f"link:{link['link_id']}" for link in topology.get("links", []) if link.get("link_id")),
    }


@app.post("/api/v1/diagnoses/{session_id}/review")
async def review_async_diagnosis(
    session_id: str,
    request: DiagnosisReviewRequest,
) -> Dict[str, Any]:
    state = store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="diagnosis session not found")
    if state.get("status") not in {"success", "degraded"} or not state.get("response"):
        raise HTTPException(status_code=409, detail="diagnosis has no reviewable result")
    if request.decision not in {"confirmed", "corrected", "expert_review_requested"}:
        raise HTTPException(status_code=422, detail="unsupported review decision")

    prediction = state["response"].get("root_cause") or {}
    ground_truth: Dict[str, Any] | None = None
    if request.decision == "confirmed":
        root_cause = prediction.get("root_cause")
        if not root_cause:
            raise HTTPException(status_code=422, detail="degraded result has no root cause to confirm")
        ground_truth = {"root_cause": root_cause}
    elif request.decision == "corrected":
        root_cause = (request.ground_truth or {}).get("root_cause")
        if not root_cause:
            raise HTTPException(status_code=422, detail="corrected review requires ground_truth.root_cause")
        topology = state.get("input", {}).get("topology", {})
        if root_cause not in _topology_root_ids(topology):
            raise HTTPException(status_code=422, detail="ground truth must reference the business topology")
        ground_truth = {"root_cause": root_cause}
    elif request.ground_truth is not None:
        raise HTTPException(status_code=422, detail="expert review request cannot include ground truth")

    reviewed_at = datetime.now(timezone.utc).isoformat()
    review = {
        "status": request.decision,
        "ground_truth": ground_truth,
        "notes": request.notes,
        "reviewed_at": reviewed_at,
    }
    state["human_decision"] = request.decision
    state["human_review"] = review
    store.upsert_session(session_id, state["status"], state)
    store.add_event(
        session_id,
        "human.reviewed",
        {
            "type": "human.reviewed",
            "timestamp": reviewed_at,
            "review": review,
        },
    )
    _archive_from_response(
        state["dossier_id"],
        state,
        state["response"],
        request.decision,
        request.notes,
        ground_truth,
    )
    return {"session_id": session_id, "dossier_id": state["dossier_id"], "review": review}


@app.get("/api/v1/examples/demo")
async def get_demo_example() -> Dict[str, Any]:
    demo_dir = Path(__file__).resolve().parents[3] / "demo"
    try:
        return {
            "alarm_filename": "alarm1.csv",
            "alarm_content": (demo_dir / "alarm1.csv").read_text(encoding="utf-8-sig"),
            "topology_filename": "topology.json",
            "topology": json.loads((demo_dir / "topology.json").read_text(encoding="utf-8")),
            "expected": json.loads((demo_dir / "expected.json").read_text(encoding="utf-8")),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="demo files are incomplete") from exc


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
        store.add_event(session_id, "rejected", {"notes": notes})
    else:
        state["status"] = "escalated"
        store.add_event(session_id, "escalated", {"notes": notes})

    store.upsert_session(session_id, state["status"], state)

    # Archive human-closed cases as structured dossiers.
    dossier_id = state.get("dossier_id") or f"DOS-HUMAN-{session_id}"
    if state.get("response"):
        _archive_from_response(dossier_id, state, state["response"], decision, notes)

    return {"session_id": session_id, "status": state["status"]}


@app.get("/v1/dossier/{dossier_id}")
async def get_dossier(dossier_id: str) -> Dict[str, Any]:
    dossier = store.get_session(dossier_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="dossier not found")
    return dossier


class EvaluateRequest(BaseModel):
    dossier_ids: List[str]


class GEPARequest(BaseModel):
    evaluation_id: str
    population_size: int = 5
    max_generations: int = 10
    elite_ratio: float = 0.4


@app.post("/v1/gepa")
async def create_gepa_optimization(request: GEPARequest) -> Dict[str, Any]:
    report = store.get_session(request.evaluation_id)
    if report is None:
        raise HTTPException(status_code=404, detail="evaluation not found")

    optimization_id = gepa.optimize(
        request.evaluation_id,
        population_size=request.population_size,
        max_generations=request.max_generations,
        elite_ratio=request.elite_ratio,
    )
    return {
        "optimization_id": optimization_id,
        "status": "completed",
        "report_url": f"/v1/gepa/{optimization_id}",
    }


@app.get("/v1/gepa/{optimization_id}")
async def get_gepa_optimization(optimization_id: str) -> Dict[str, Any]:
    report = store.get_session(optimization_id)
    if report is None:
        raise HTTPException(status_code=404, detail="optimization not found")
    return report


@app.post("/v1/evaluate")
async def create_evaluation(request: EvaluateRequest) -> Dict[str, Any]:
    if not request.dossier_ids:
        raise HTTPException(status_code=400, detail="dossier_ids cannot be empty")
    report = evaluator.evaluate(request.dossier_ids)
    return {
        "evaluation_id": report["evaluation_id"],
        "status": report["status"],
        "report_url": f"/v1/evaluate/{report['evaluation_id']}",
    }


@app.get("/v1/evaluate/{evaluation_id}")
async def get_evaluation(evaluation_id: str) -> Dict[str, Any]:
    report = store.get_session(evaluation_id)
    if report is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    return report


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
