"""Runtime tool registry."""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import Field

from core.contracts.base import ContractBaseModel

ToolHandler = Callable[..., Awaitable[Any]]


class ToolDefinition(ContractBaseModel):
    """Tool metadata and async handler."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    handler: ToolHandler
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolRegistry:
    """In-memory async registry for runtime tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    async def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    async def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool not registered: {name}") from exc

    async def list(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools[name] for name in sorted(self._tools))

    async def names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in await self.list())

