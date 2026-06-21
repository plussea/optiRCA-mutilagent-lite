from typing import Any, Dict

from langgraph.graph import END, StateGraph

from optirc_lite.runtime.agent_runtime import AgentRuntime
from optirc_lite.skills.builtin import create_builtin_skills
from optirc_lite.tools.builtin import create_builtin_tools
from optirc_lite.workflow.state import AgentState

runtime = AgentRuntime(skills=create_builtin_skills(), tools=create_builtin_tools())


async def perception_node(state: AgentState) -> Dict[str, Any]:
    result = await runtime.run_phase("perception", state)
    return {**result, "status": "perceived"}


async def diagnosis_node(state: AgentState) -> Dict[str, Any]:
    result = await runtime.run_phase("diagnosis", state)
    return {**result, "status": "diagnosed"}


async def validation_node(state: AgentState) -> Dict[str, Any]:
    result = await runtime.run_phase("validation", state)
    return {**result, "status": "diagnosis_validated", "retry_count": state.get("retry_count", 0) + 1}


async def planning_node(state: AgentState) -> Dict[str, Any]:
    result = await runtime.run_phase("planning", state)
    return {**result, "status": "planned"}


async def solution_validation_node(state: AgentState) -> Dict[str, Any]:
    result = await runtime.run_phase("solution_validation", state)
    return {**result, "status": "solution_validated"}


async def human_review_node(state: AgentState) -> Dict[str, Any]:
    package = {
        "diagnosis": state.get("diagnosis", {}),
        "planning": state.get("planning", {}),
        "diagnosis_validation": state.get("validation", {}),
        "solution_validation": state.get("solution_validation", {}),
    }
    return {
        "status": "waiting_review",
        "pending_human": True,
        "human_review": {"package": package, "decision": None},
    }


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
