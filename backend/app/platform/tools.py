from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ConfigDict


class RegisteredTool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[Any]]


async def echo_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the provided arguments unchanged."""

    return {"echo": arguments}


async def time_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return current UTC time. Ignores external command execution entirely."""

    _ = arguments
    return {"utc": datetime.now(UTC).isoformat()}


TOOLS: dict[str, RegisteredTool] = {
    "echo_tool": RegisteredTool(
        name="echo_tool",
        description="Returns the provided JSON arguments. Safe mock tool.",
        input_schema={"type": "object", "additionalProperties": True},
        handler=echo_tool,
    ),
    "time_tool": RegisteredTool(
        name="time_tool",
        description="Returns current UTC time. Safe mock tool.",
        input_schema={"type": "object", "additionalProperties": True},
        handler=time_tool,
    ),
}


def list_registered_tools() -> list[RegisteredTool]:
    return list(TOOLS.values())


def get_registered_tool(tool_name: str) -> RegisteredTool | None:
    return TOOLS.get(tool_name)
