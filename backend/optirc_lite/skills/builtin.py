from optirc_lite.skills.closure import KnowledgeClosureSkill
from optirc_lite.skills.critic import DiagnosisCriticSkill, SolutionCriticSkill
from optirc_lite.skills.diagnosis import RootCauseDiagnosisSkill
from optirc_lite.skills.perception import AlarmPerceptionSkill
from optirc_lite.skills.planning import RepairPlanningSkill
from optirc_lite.skills.registry import SkillRegistry


def create_builtin_skills() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(AlarmPerceptionSkill())
    registry.register(RootCauseDiagnosisSkill())
    registry.register(DiagnosisCriticSkill())
    registry.register(RepairPlanningSkill())
    registry.register(SolutionCriticSkill())
    registry.register(KnowledgeClosureSkill())
    return registry
