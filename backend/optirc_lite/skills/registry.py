from typing import Dict, List

from optirc_lite.skills.base import Skill
from optirc_lite.workflow.state import AgentState


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"Skill not registered: {name}")
        return self._skills[name]

    async def rank(self, state: AgentState, phase: str) -> List[tuple[str, float]]:
        scored = []
        for name, skill in self._skills.items():
            if not name.startswith(f"{phase}."):
                continue
            score = await skill.can_handle(state)
            if score > 0:
                scored.append((name, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored
