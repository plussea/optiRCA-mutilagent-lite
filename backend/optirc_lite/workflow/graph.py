from typing import Any, Dict

from langgraph.graph import END, StateGraph

from optirc_lite.runtime.agent_runtime import AgentRuntime
from optirc_lite.skills.builtin import create_builtin_skills
from optirc_lite.storage.sqlite_store import store
from optirc_lite.tools.builtin import create_builtin_tools
from optirc_lite.workflow.state import AgentState

runtime = AgentRuntime(skills=create_builtin_skills(), tools=create_builtin_tools())


def _record_event(state: AgentState, phase: str, event: str, payload: Dict[str, Any]) -> None:
    session_id = state.get("session_id")
    if not session_id:
        return
    if event == "start":
        running_state = {**state, "status": f"{phase}_running"}
        store.upsert_session(session_id, running_state["status"], running_state)
    store.add_event(session_id, f"{phase}.{event}", payload)


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
    return update


async def perception_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "perception", "start", {"input": {"raw_input": state.get("raw_input")}})
    result = await runtime.run_phase("perception", state)
    return _finish_phase(state, "perception", {**result, "status": "perceived"})


async def diagnosis_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "diagnosis", "start", {"input": state.get("perception", {})})
    result = await runtime.run_phase("diagnosis", state)
    return _finish_phase(state, "diagnosis", {**result, "status": "diagnosed"})


async def validation_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "validation", "start", {"input": state.get("diagnosis", {})})
    result = await runtime.run_phase("validation", state)
    return _finish_phase(
        state,
        "validation",
        {**result, "status": "diagnosis_validated", "retry_count": state.get("retry_count", 0) + 1},
    )


async def planning_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "planning", "start", {"input": state.get("diagnosis", {})})
    result = await runtime.run_phase("planning", state)
    return _finish_phase(state, "planning", {**result, "status": "planned"})


async def solution_validation_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "solution_validation", "start", {"input": state.get("planning", {})})
    result = await runtime.run_phase("solution_validation", state)
    return _finish_phase(state, "solution_validation", {**result, "status": "solution_validated"})


async def human_review_node(state: AgentState) -> Dict[str, Any]:
    _record_event(state, "human_review", "start", {"input": state.get("solution_validation", {})})
    package = {
        "diagnosis": state.get("diagnosis", {}),
        "planning": state.get("planning", {}),
        "diagnosis_validation": state.get("validation", {}),
        "solution_validation": state.get("solution_validation", {}),
    }
    update = {
        "status": "waiting_review",
        "pending_human": True,
        "human_review": {"package": package, "decision": None},
    }
    return _finish_phase(state, "human_review", update)


def route_validation(state: AgentState) -> str:
    validation = state.get("validation", {})
    if validation.get("suggested_action") == "needs_human":
        return "human_review"
    return "planning"


def build_workflow():
    graph = StateGraph(AgentState)
    graph.add_node("perception", perception_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("validation", validation_node)
    graph.add_node("planning", planning_node)
    graph.add_node("solution_validation", solution_validation_node)
    graph.add_node("human_review", human_review_node)

    graph.set_entry_point("perception")
    graph.add_edge("perception", "diagnosis")
    graph.add_edge("diagnosis", "validation")
    graph.add_conditional_edges(
        "validation",
        route_validation,
        {"planning": "planning", "human_review": "human_review"},
    )
    graph.add_edge("planning", "solution_validation")
    graph.add_edge("solution_validation", "human_review")
    graph.add_edge("human_review", END)
    return graph.compile()
