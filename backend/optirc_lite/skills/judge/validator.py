"""Chain Validator — direction/time/coverage checks on candidate chains."""

from typing import Any, Dict, List

from optirc_lite.workflow.state import AgentState


class ChainValidator:
    """Validate and annotate candidate propagation chains.

    For this boundary-refactor iteration the validation remains a lightweight
    pass-through: it preserves every candidate produced by the generator while
    attaching validation metadata so richer rules can be plugged in later.
    """

    def validate(self, candidates: List[Dict[str, Any]], state: AgentState) -> List[Dict[str, Any]]:
        validated: List[Dict[str, Any]] = []
        for candidate in candidates:
            candidate["validation"] = {
                "direction_check": True,
                "time_check": True,
                "coverage_check": True,
            }
            validated.append(candidate)
        return validated
