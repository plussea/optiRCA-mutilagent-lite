from typing import Any, Dict, List, Protocol, Type

from pydantic import BaseModel, Field

from optirc_lite.tools.registry import ToolRegistry
from optirc_lite.workflow.state import AgentState


class SkillInput(BaseModel):
    state: Dict[str, Any] = Field(default_factory=dict)


class SkillObservation(BaseModel):
    type: str
    value: Any = None
    docs: List[Dict[str, Any]] | None = None
    graph: Dict[str, Any] | None = None


class SkillOutput(BaseModel):
    result: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    evidence: List[str] = Field(default_factory=list)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    next_suggestions: List[str] = Field(default_factory=list)


class Skill(Protocol):
    name: str
    description: str
    required_tools: List[str]
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]

    async def can_handle(self, state: AgentState) -> float:
        ...

    async def run(self, state: AgentState, tools: ToolRegistry) -> SkillOutput:
        ...
