import asyncio
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict


class RegisteredTool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[Any]]
    default_timeout_seconds: float = 5.0
    native_type: Literal["mock", "agentscope_tool", "mcp", "skill"] = "mock"
    native_ref: str | None = None
    enabled: bool = True

    @property
    def timeout_seconds(self) -> float:
        return self.default_timeout_seconds


async def echo_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the provided arguments unchanged."""

    return {"echo": arguments}


async def time_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return current UTC time. Ignores external command execution entirely."""

    _ = arguments
    return {"utc": datetime.now(UTC).isoformat()}


async def slow_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Sleep for a bounded duration to test timeout behavior safely."""

    requested = arguments.get("sleep_seconds", 2)
    try:
        sleep_seconds = float(requested)
    except (TypeError, ValueError):
        sleep_seconds = 2.0
    sleep_seconds = max(0.0, min(sleep_seconds, 10.0))
    await asyncio.sleep(sleep_seconds)
    return {"slept_seconds": sleep_seconds}


TOOLS: dict[str, RegisteredTool] = {
    "echo_tool": RegisteredTool(
        name="echo_tool",
        description="Returns the provided JSON arguments. Safe mock tool.",
        input_schema={"type": "object", "additionalProperties": True},
        handler=echo_tool,
        default_timeout_seconds=5.0,
        native_type="mock",
        native_ref=None,
        enabled=True,
    ),
    "time_tool": RegisteredTool(
        name="time_tool",
        description="Returns current UTC time. Safe mock tool.",
        input_schema={"type": "object", "additionalProperties": True},
        handler=time_tool,
        default_timeout_seconds=5.0,
        native_type="mock",
        native_ref=None,
        enabled=True,
    ),
    "slow_tool": RegisteredTool(
        name="slow_tool",
        description="Sleeps for up to 10 seconds. Safe mock tool for timeout tests.",
        input_schema={
            "type": "object",
            "properties": {"sleep_seconds": {"type": "number"}},
            "additionalProperties": False,
        },
        handler=slow_tool,
        default_timeout_seconds=1.0,
        native_type="mock",
        native_ref=None,
        enabled=True,
    ),
}


def list_registered_tools() -> list[RegisteredTool]:
    return list(TOOLS.values())


def get_registered_tool(tool_name: str) -> RegisteredTool | None:
    return TOOLS.get(tool_name)
