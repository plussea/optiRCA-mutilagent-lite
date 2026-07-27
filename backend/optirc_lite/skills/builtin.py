from optirc_lite.skills.closure import KnowledgeClosureSkill
from optirc_lite.skills.critic import DiagnosisCriticSkill, SolutionCriticSkill
from optirc_lite.skills.diagnosis import RootCauseDiagnosisSkill
from optirc_lite.skills.judge import PropagationJudgeSkill
from optirc_lite.skills.perception import AlarmPerceptionSkill
from optirc_lite.skills.planning import RepairPlanningSkill
from optirc_lite.skills.rank import RootCauseRankerSkill
from optirc_lite.skills.registry import SkillRegistry
from optirc_lite.skills.topology import TopologyBuilderSkill


def create_builtin_skills() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(AlarmPerceptionSkill())
    registry.register(TopologyBuilderSkill())
    registry.register(PropagationJudgeSkill())
    registry.register(RootCauseRankerSkill())
    registry.register(RootCauseDiagnosisSkill())
    registry.register(DiagnosisCriticSkill())
    registry.register(RepairPlanningSkill())
    registry.register(SolutionCriticSkill())
    registry.register(KnowledgeClosureSkill())
    return registry
