from datetime import datetime, timezone
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from optirc_lite.runtime.agent_runtime import AgentRuntime
from optirc_lite.skills.builtin import create_builtin_skills
from optirc_lite.storage.evidence_graph import EvidenceGraph
from optirc_lite.storage.sqlite_store import store
from optirc_lite.tools.builtin import create_builtin_tools
from optirc_lite.workflow.state import AgentState

runtime = AgentRuntime(skills=create_builtin_skills(), tools=create_builtin_tools())

STAGE_SUMMARIES = {
    "perception": "告警文件已解析为结构化事实表",
    "topology": "业务拓扑与告警证据已关联",
    "judge": "传播关系已生成根因假设",
    "rank": "候选根因已完成多维排序",
    "critic": "候选根因已完成可信度复核",
    "dossier": "诊断结论与证据已写入案卷",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(session_id: str, phase: str) -> int:
    starts = [
        event
        for event in store.list_events(session_id)
        if event["phase"] == f"{phase}.start"
    ]
    if not starts:
        return 0
    started_at = datetime.fromisoformat(starts[-1]["created_at"])
    return max(0, int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000))


def _critic_checks(critic: Dict[str, Any]) -> list[Dict[str, Any]]:
    reasons = [str(reason) for reason in critic.get("reasons", [])]
    reason_text = " ".join(reasons).lower()
    checks = [
        (
            "alarm_coverage",
            "告警解释完整性",
            not any(token in reason_text for token in ("unexplained", "leaves")),
        ),
        (
            "endpoint_consistency",
            "链路两端一致性",
            "bidirectional" not in reason_text,
        ),
        (
            "single_fault",
            "单一故障合理性",
            "cluster" not in reason_text,
        ),
    ]
    return [
        {
            "id": check_id,
            "label": label,
            "passed": passed,
            "reason": "；".join(reasons) if not passed else "本轮反事实检查通过",
        }
        for check_id, label, passed in checks
    ]


def _record_event(state: AgentState, phase: str, event: str, payload: Dict[str, Any]) -> None:
    session_id = state.get("session_id")
    if not session_id:
        return
    if event == "start":
        running_state = {**state, "status": f"{phase}_running"}
        store.upsert_session(session_id, running_state["status"], running_state)
        event_payload = {
            "type": "stage.started",
            "stage": phase,
            "timestamp": _utc_now(),
            **payload,
        }
    else:
        event_payload = {
            "type": "stage.completed",
            "stage": phase,
            "timestamp": _utc_now(),
            "elapsed_ms": _elapsed_ms(session_id, phase),
            "summary": STAGE_SUMMARIES.get(phase, f"{phase} 已完成"),
            "artifact": payload,
        }
    store.add_event(session_id, f"{phase}.{event}", event_payload)


def _finish_phase(state: AgentState, phase: str, update: Dict[str, Any]) -> Dict[str, Any]:
    next_state = {**state, **update}
    session_id = state.get("session_id")
    if session_id:
        store.upsert_session(session_id, next_state.get("status", "unknown"), next_state)
    _record_event(
        next_state,
        phase,
        "end",
        {
            "status": next_state.get("status"),
            "output": next_state.get(phase) or next_state.get("human_review"),
            "decision_trace": next_state.get("decision_trace", [])[-1:],
            "tool_calls": next_state.get("tool_calls", [])[-1:],
        },
    )
    timestamp = _utc_now()
    if phase == "topology":
        store.add_event(
            session_id,
            "topology.updated",
            {
                "type": "topology.updated",
                "timestamp": timestamp,
                "topology": next_state.get("topology", {}),
            },
        )
    elif phase == "rank":
        store.add_event(
            session_id,
            "candidates.updated",
            {
                "type": "candidates.updated",
                "timestamp": timestamp,
                "candidates": next_state.get("candidates", []),
            },
        )
    elif phase == "critic":
        critic = next_state.get("critic", {})
        store.add_event(
            session_id,
            "critic.checked",
            {
                "type": "critic.checked",
                "timestamp": timestamp,
                "checks": _critic_checks(critic),
                "verdict": critic.get("verdict"),
                "fallback_action": critic.get("fallback_action"),
            },
        )
    return update


def _current_evidence_graph() -> Dict[str, Any]:
    return EvidenceGraph()._read()


async def perception_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "perception", "start", {"input": {"raw_input": state.get("raw_input")}})
    try:
        result = await runtime.run_phase("perception", state)
        update = _finish_phase(state, "perception", {**result, "status": "perceived"})
        perception = update.get("perception", {})
        if not perception:
            return {**update, "degradation_reason": "agent_failure"}
        return update
    except Exception as exc:
        return {"status": "degraded", "degradation_reason": "agent_failure", "error_message": str(exc)}


async def topology_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "topology", "start", {"input": state.get("topology", {})})
    try:
        result = await runtime.run_phase("topology", state)
        update = _finish_phase(state, "topology", {**result, "status": "topology_built"})
        topology = update.get("topology", {})
        if not topology:
            return {**update, "degradation_reason": "agent_failure"}
        update["evidence_graph"] = _current_evidence_graph()
        if state.get("perception", {}).get("alarm_count", 0) == 0:
            update["degradation_reason"] = "agent_failure"
        return update
    except Exception as exc:
        return {"status": "degraded", "degradation_reason": "agent_failure", "error_message": str(exc)}


def guard_empty_alarms(state: AgentState) -> str:
    alarm_count = state.get("perception", {}).get("alarm_count", 0)
    if alarm_count == 0:
        state["degradation_reason"] = "agent_failure"
        return "assemble_degraded"
    return "judge"


async def judge_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "judge", "start", {"input": state.get("evidence_graph", {})})
    try:
        result = await runtime.run_phase("judge", state)
        update = _finish_phase(state, "judge", {**result, "status": "judged"})
        judge = update.get("judge", {})
        if not judge or not judge.get("candidates"):
            return {**update, "degradation_reason": "judge_timeout"}
        update["evidence_graph"] = _current_evidence_graph()
        return update
    except Exception as exc:
        return {"status": "degraded", "degradation_reason": "judge_timeout", "error_message": str(exc)}


async def rank_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "rank", "start", {"input": state.get("judge", {})})
    try:
        result = await runtime.run_phase("rank", state)
        rank = result.get("rank", {})
        if not rank:
            return {**result, "status": "ranked", "degradation_reason": "ranker_timeout"}
        update = _finish_phase(
            state,
            "rank",
            {
                **result,
                "status": "ranked",
                "candidates": rank.get("candidates", []),
            },
        )
        update["evidence_graph"] = _current_evidence_graph()
        return update
    except Exception as exc:
        return {"status": "degraded", "degradation_reason": "ranker_timeout", "error_message": str(exc)}


async def critic_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "critic", "start", {"input": state.get("candidates", [])})
    try:
        current_round = state.get("fallback_round", 0)
        result = await runtime.run_phase("critic", state)
        update = _finish_phase(state, "critic", {**result, "status": "criticized", "fallback_round": current_round + 1})
        update["evidence_graph"] = _current_evidence_graph()
        return update
    except Exception as exc:
        return {"status": "degraded", "degradation_reason": "critic_timeout", "error_message": str(exc)}


def route_after_critic(state: AgentState) -> str:
    critic = state.get("critic", {})
    if critic.get("verdict") == "pass":
        return "assemble_success"

    max_rounds = state.get("max_fallback_rounds", 0)
    current_round = state.get("fallback_round", 0)
    if current_round >= max_rounds + 1:
        return "assemble_degraded"

    action = critic.get("fallback_action")
    if action == "FALLBACK_TO_JUDGE":
        return "judge"
    if action == "FALLBACK_TO_RANKER":
        return "rank"

    return "assemble_degraded"


def _build_success_response(state: AgentState) -> Dict[str, Any]:
    candidates = state.get("candidates", [])
    top = candidates[0] if candidates else {}
    return {
        "status": "success",
        "dossier_id": state.get("dossier_id"),
        "session_id": state.get("session_id"),
        "root_cause": top,
        "evidence_chain": top.get("evidence_chain", []),
        "confidence": top.get("confidence", 0.0),
        "suggestion": "复核通过，建议按排名最高的候选根因处理。",
        "requires_human_review": False,
        "input": state.get("input", {}),
        "evidence_graph": state.get("evidence_graph", {"nodes": [], "edges": []}),
        "candidates": candidates,
        "critic_checks": _critic_checks(state.get("critic", {})),
        "critic_verdict": "pass",
        "metadata": {
            "phases_completed": ["perception", "topology", "judge", "rank", "critic"],
            "fallback_rounds": state.get("fallback_round", 0) - 1,
            "diagnosed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _build_degraded_response(state: AgentState) -> Dict[str, Any]:
    reason = state.get("degradation_reason", "agent_failure")
    return {
        "status": "degraded",
        "dossier_id": state.get("dossier_id"),
        "session_id": state.get("session_id"),
        "root_cause": {},
        "evidence_chain": [],
        "confidence": 0.0,
        "suggestion": "自动推理降级，请人工复核拓扑与告警时间线。",
        "requires_human_review": True,
        "degradation_reason": reason,
        "input": state.get("input", {}),
        "evidence_graph": state.get("evidence_graph", {"nodes": [], "edges": []}),
        "candidates": state.get("candidates", []),
        "critic_checks": _critic_checks(state.get("critic", {})),
        "critic_verdict": state.get("critic", {}).get("verdict") if state.get("critic") else None,
        "error": state.get("error_message"),
    }


def _persist_dossier(state: AgentState) -> None:
    response = state.get("response", {})
    candidates = state.get("candidates", [])
    top = candidates[0] if candidates else None
    store.upsert_dossier(
        dossier_id=state.get("dossier_id", "unknown"),
        session_id=state.get("session_id", "unknown"),
        status=response.get("status", "degraded"),
        input_payload=state.get("input", {}),
        evidence_graph=state.get("evidence_graph", {"nodes": [], "edges": []}),
        top_candidate=top,
        critic_verdict=response.get("critic_verdict"),
        degradation_reason=response.get("degradation_reason"),
        confidence=response.get("confidence", 0.0),
        requires_human_review=response.get("requires_human_review", True),
    )


async def assemble_success_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "dossier", "start", {"input": {"dossier_id": state.get("dossier_id")}})
    response = _build_success_response(state)
    update = {
        "status": "success",
        "response": response,
    }
    next_state = {**state, **update}
    _persist_dossier(next_state)
    return _finish_phase(state, "dossier", update)


async def assemble_degraded_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "dossier", "start", {"input": {"dossier_id": state.get("dossier_id")}})
    if not state.get("degradation_reason"):
        critic = state.get("critic", {})
        max_rounds = state.get("max_fallback_rounds", 0)
        current_round = state.get("fallback_round", 0)
        if current_round >= max_rounds + 1 and critic.get("verdict") != "pass":
            state["degradation_reason"] = "max_fallback_exceeded"
        else:
            state["degradation_reason"] = "critic_timeout"
    response = _build_degraded_response(state)
    update = {
        "status": "degraded",
        "response": response,
    }
    next_state = {**state, **update}
    _persist_dossier(next_state)
    return _finish_phase(state, "dossier", update)


def route_degradation(state: AgentState) -> str:
    if state.get("degradation_reason"):
        return "assemble_degraded"
    return "continue"


def build_workflow():
    graph = StateGraph(AgentState)
    graph.add_node("perception", perception_node)
    graph.add_node("topology", topology_node)
    graph.add_node("judge", judge_node)
    graph.add_node("rank", rank_node)
    graph.add_node("critic", critic_node)
    graph.add_node("assemble_success", assemble_success_node)
    graph.add_node("assemble_degraded", assemble_degraded_node)

    graph.set_entry_point("perception")
    graph.add_conditional_edges(
        "perception",
        route_degradation,
        {"assemble_degraded": "assemble_degraded", "continue": "topology"},
    )
    graph.add_conditional_edges(
        "topology",
        guard_empty_alarms,
        {"assemble_degraded": "assemble_degraded", "judge": "judge"},
    )
    graph.add_conditional_edges(
        "judge",
        route_degradation,
        {"assemble_degraded": "assemble_degraded", "continue": "rank"},
    )
    graph.add_conditional_edges(
        "rank",
        route_degradation,
        {"assemble_degraded": "assemble_degraded", "continue": "critic"},
    )
    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "assemble_success": "assemble_success",
            "assemble_degraded": "assemble_degraded",
            "judge": "judge",
            "rank": "rank",
        },
    )
    graph.add_edge("assemble_success", END)
    graph.add_edge("assemble_degraded", END)
    return graph.compile()
