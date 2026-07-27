from typing import Any, Dict, List

from pydantic import BaseModel, Field

from optirc_lite.skills.base import SkillInput, SkillOutput


class PerceptionResult(BaseModel):
    input_name: str = ""
    alarm_count: int = 0
    alarms: List[Dict[str, Any]] = Field(default_factory=list)
    headers: List[str] = Field(default_factory=list)
    first_row: Dict[str, Any] = Field(default_factory=dict)
    alarm_types: List[str] = Field(default_factory=list)
    devices: List[str] = Field(default_factory=list)
    primary_alarm: str = "unknown"
    primary_device: str = ""
    description: str = ""


class PerceptionSkillOutput(SkillOutput):
    result: PerceptionResult = Field(default_factory=PerceptionResult)


class DiagnosisResult(BaseModel):
    root_cause: str = "unknown"
    confidence: float = 0.0
    evidence: List[str] = Field(default_factory=list)
    recommended_action: str = ""
    retrieved_docs: List[Dict[str, Any]] = Field(default_factory=list)
    topology_context: Dict[str, Any] = Field(default_factory=dict)
    llm_used: bool = False


class DiagnosisSkillOutput(SkillOutput):
    result: DiagnosisResult = Field(default_factory=DiagnosisResult)


class ValidationResult(BaseModel):
    validation_passed: bool = False
    score: float = 0.0
    notes: str = ""
    suggested_action: str = "needs_human"


class ValidationSkillOutput(SkillOutput):
    result: ValidationResult = Field(default_factory=ValidationResult)


class Plan(BaseModel):
    title: str = ""
    steps: List[str] = Field(default_factory=list)
    estimated_time: str = ""
    required_resources: List[str] = Field(default_factory=list)
    sops: List[Dict[str, Any]] = Field(default_factory=list)


class PlanningResult(BaseModel):
    final_plan: Plan = Field(default_factory=Plan)
    rollback_procedure: str = ""
    llm_used: bool = False


class PlanningSkillOutput(SkillOutput):
    result: PlanningResult = Field(default_factory=PlanningResult)


class SolutionValidationResult(BaseModel):
    solution_valid: bool = False
    risk_level: str = "high"
    notes: str = ""
    needs_replan: bool = True


class SolutionValidationSkillOutput(SkillOutput):
    result: SolutionValidationResult = Field(default_factory=SolutionValidationResult)


class ClosureResult(BaseModel):
    stored: bool = False
    summary: str = ""


class ClosureSkillOutput(SkillOutput):
    result: ClosureResult = Field(default_factory=ClosureResult)


DefaultSkillInput = SkillInput
