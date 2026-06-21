from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    session_id: str
    raw_input: str
    status: str
    pending_human: bool
    human_decision: Optional[str]
    retry_count: int

    perception: Dict[str, Any]
    diagnosis: Dict[str, Any]
    diagnosis_validation: Dict[str, Any]
    planning: Dict[str, Any]
    solution_validation: Dict[str, Any]
    human_review: Dict[str, Any]
    closure: Dict[str, Any]

    runtime_context: Dict[str, Any]
    observations: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    decision_trace: List[Dict[str, Any]]
    error_message: Optional[str]
