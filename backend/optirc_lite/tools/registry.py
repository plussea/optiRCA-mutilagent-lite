from typing import Any, Awaitable, Callable, Dict


ToolFn = Callable[..., Awaitable[Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolFn] = {}

    def register(self, name: str, tool: ToolFn) -> None:
        self._tools[name] = tool

    async def call(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return await self._tools[name](**kwargs)

    def names(self) -> list[str]:
        return sorted(self._tools.keys())
