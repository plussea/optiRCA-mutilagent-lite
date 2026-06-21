from typing import Any, Protocol


class Tool(Protocol):
    name: str
    description: str

    async def __call__(self, **kwargs: Any) -> Any:
        ...
