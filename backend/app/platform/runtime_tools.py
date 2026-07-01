import logging

from agentscope.tool import FunctionTool, ToolBase

from backend.app.config import Settings, get_settings
from backend.app.platform.runtime_permissions import (
    ensure_runtime_tool_allowed,
    is_runtime_tool_allowed,
    parse_scoped_user_id,
)
from backend.app.platform.tools import get_registered_tool


logger = logging.getLogger(__name__)

RUNTIME_ECHO_TOOL_NAME = "runtime_echo_tool"
ENABLED_MOCK_MODES = {"mock", "mock_safe", "runtime_echo"}


def make_runtime_echo_callable(
    settings: Settings,
    scoped_user_id: str,
    agent_id: str,
    session_id: str,
    tool_name: str = RUNTIME_ECHO_TOOL_NAME,
):
    """Create a safe echo callable with runtime permission bound in."""

    async def runtime_echo_text(text: str) -> dict[str, str]:
        """Return text only. No file, network, env, or command access."""

        ensure_runtime_tool_allowed(
            scoped_user_id,
            agent_id,
            session_id,
            tool_name,
            settings=settings,
        )
        return {"text": str(text)}

    return runtime_echo_text


def build_runtime_echo_tool(
    settings: Settings,
    scoped_user_id: str,
    agent_id: str,
    session_id: str,
) -> FunctionTool:
    """Build a safe AgentScope FunctionTool for runtime adapter smoke tests."""

    return FunctionTool(
        func=make_runtime_echo_callable(
            settings,
            scoped_user_id,
            agent_id,
            session_id,
        ),
        name=RUNTIME_ECHO_TOOL_NAME,
        description=(
            "Return the provided text. Safe runtime smoke-test tool with no "
            "file, network, environment, or command access."
        ),
        is_concurrency_safe=True,
        is_read_only=True,
    )


async def build_extra_agent_tools(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    """Build AgentScope runtime tools for a chat turn.

    This Phase 2.3.3 skeleton is closed by default. It only supports a safe
    mock echo tool when explicitly enabled and allowed by platform permission.
    MCP, Skills, real enterprise systems, shell commands, network access, and
    file mutations are intentionally out of scope.
    """

    try:
        return await _build_extra_agent_tools(
            get_settings(),
            user_id,
            agent_id,
            session_id,
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Runtime tool adapter failed; returning no extra tools.",
        )
        return []


async def _build_extra_agent_tools(
    settings: Settings,
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    _ = session_id

    if not settings.platform_enable_runtime_tools:
        logger.debug("Runtime tools disabled by PLATFORM_ENABLE_RUNTIME_TOOLS.")
        return []

    mode = settings.platform_runtime_tools_mode.strip().lower()
    if mode == "disabled":
        logger.debug("Runtime tools disabled by PLATFORM_RUNTIME_TOOLS_MODE.")
        return []

    if mode not in ENABLED_MOCK_MODES:
        logger.warning(
            "Unsupported PLATFORM_RUNTIME_TOOLS_MODE=%s; returning no tools.",
            settings.platform_runtime_tools_mode,
        )
        return []

    parsed_user = parse_scoped_user_id(user_id)
    if parsed_user is None:
        logger.warning(
            "Runtime tools require scoped user id tenant_id:user_id; got %r.",
            user_id,
        )
        return []

    tenant_id, real_user_id = parsed_user

    tool = get_registered_tool(RUNTIME_ECHO_TOOL_NAME)
    if tool is None or not tool.enabled:
        logger.debug("Runtime echo tool is not registered or disabled.")
        return []

    if not is_runtime_tool_allowed(
        user_id,
        agent_id,
        session_id,
        RUNTIME_ECHO_TOOL_NAME,
        settings=settings,
    ):
        logger.debug(
            "Runtime echo tool not injected because permission denied.",
        )
        return []

    logger.info(
        "Injecting safe runtime echo tool for tenant=%s user=%s agent=%s.",
        tenant_id,
        real_user_id,
        agent_id,
    )
    return [build_runtime_echo_tool(settings, user_id, agent_id, session_id)]
