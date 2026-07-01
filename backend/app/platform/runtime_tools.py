import logging

from agentscope.tool import FunctionTool, ToolBase

from backend.app.config import Settings, get_settings
from backend.app.platform.permissions import is_tool_allowed
from backend.app.platform.security import ScopedUser
from backend.app.platform.tools import get_registered_tool


logger = logging.getLogger(__name__)

RUNTIME_ECHO_TOOL_NAME = "runtime_echo_tool"
ENABLED_MOCK_MODES = {"mock", "mock_safe", "runtime_echo"}


def parse_scoped_user_id(scoped_user_id: str) -> tuple[str, str] | None:
    """Parse the platform scoped user id format: tenant_id:user_id."""

    tenant_id, separator, user_id = scoped_user_id.partition(":")
    if not separator or not tenant_id.strip() or not user_id.strip():
        return None
    return tenant_id.strip(), user_id.strip()


async def runtime_echo_text(text: str) -> dict[str, str]:
    """Return text only. No file, network, env, or command access."""

    return {"text": str(text)}


def build_runtime_echo_tool() -> FunctionTool:
    """Build a safe AgentScope FunctionTool for runtime adapter smoke tests."""

    return FunctionTool(
        func=runtime_echo_text,
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
    scoped_user = ScopedUser(
        tenant_id=tenant_id,
        user_id=real_user_id,
        scoped_user_id=user_id,
    )

    tool = get_registered_tool(RUNTIME_ECHO_TOOL_NAME)
    if tool is None or not tool.enabled:
        logger.debug("Runtime echo tool is not registered or disabled.")
        return []

    if not is_tool_allowed(
        settings,
        scoped_user,
        agent_id,
        RUNTIME_ECHO_TOOL_NAME,
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
    return [build_runtime_echo_tool()]
