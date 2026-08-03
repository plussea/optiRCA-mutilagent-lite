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

    # New heterogeneous evidence-graph diagnosis pipeline
    topology: Dict[str, Any]
    evidence_graph: Dict[str, Any]
    judge: Dict[str, Any]
    rank: Dict[str, Any]
    candidates: List[Dict[str, Any]]
    critic: Dict[str, Any]
    max_fallback_rounds: int
    fallback_round: int
    degradation_reason: Optional[str]
    response: Dict[str, Any]
    dossier_id: Optional[str]
    input: Dict[str, Any]

    runtime_context: Dict[str, Any]
    observations: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    decision_trace: List[Dict[str, Any]]
    error_message: Optional[str]
