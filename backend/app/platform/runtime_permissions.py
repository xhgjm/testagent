import logging
from typing import Any, Literal

from agentscope.permission import PermissionBehavior, PermissionRule

from backend.app.config import Settings, get_settings
from backend.app.platform.permissions import is_tool_allowed
from backend.app.platform.security import ScopedUser


logger = logging.getLogger(__name__)

PermissionEffect = Literal["allow", "deny", "ask"]


class RuntimeToolPermissionDenied(PermissionError):
    """Raised when a runtime tool invocation is denied by platform policy."""

    error_code = "RUNTIME_PERMISSION_DENIED"

    def __init__(self, tool_name: str, agent_id: str, session_id: str) -> None:
        self.tool_name = tool_name
        self.agent_id = agent_id
        self.session_id = session_id
        super().__init__(
            f"Runtime tool permission denied for tool={tool_name}, "
            f"agent_id={agent_id}, session_id={session_id}.",
        )


def parse_scoped_user_id(scoped_user_id: str) -> tuple[str, str] | None:
    """Parse the platform scoped user id format: tenant_id:user_id."""

    tenant_id, separator, user_id = scoped_user_id.partition(":")
    if not separator or not tenant_id.strip() or not user_id.strip():
        return None
    return tenant_id.strip(), user_id.strip()


def build_scoped_user_from_runtime_user_id(
    scoped_user_id: str,
) -> ScopedUser | None:
    parsed = parse_scoped_user_id(scoped_user_id)
    if parsed is None:
        return None
    tenant_id, user_id = parsed
    return ScopedUser(
        tenant_id=tenant_id,
        user_id=user_id,
        scoped_user_id=scoped_user_id,
    )


def is_runtime_tool_allowed(
    scoped_user_id: str,
    agent_id: str,
    session_id: str,
    tool_name: str,
    *,
    settings: Settings | None = None,
) -> bool:
    """Check platform permission for a runtime tool call.

    The current permission granularity is tenant_id, user_id, agent_id, and
    tool_name. session_id is accepted for runtime context and future auditing.
    """

    _ = session_id
    scoped_user = build_scoped_user_from_runtime_user_id(scoped_user_id)
    if scoped_user is None:
        logger.warning(
            "Runtime tool permission denied because user id is not scoped: %r.",
            scoped_user_id,
        )
        return False

    return is_tool_allowed(
        settings or get_settings(),
        scoped_user,
        agent_id,
        tool_name,
    )


def ensure_runtime_tool_allowed(
    scoped_user_id: str,
    agent_id: str,
    session_id: str,
    tool_name: str,
    *,
    settings: Settings | None = None,
) -> None:
    if not is_runtime_tool_allowed(
        scoped_user_id,
        agent_id,
        session_id,
        tool_name,
        settings=settings,
    ):
        raise RuntimeToolPermissionDenied(tool_name, agent_id, session_id)


def build_agentscope_permission_rule_for_tool(
    tool_name: str,
    *,
    effect: PermissionEffect = "allow",
    rule_content: str | None = None,
    source: str = "agent-platform",
) -> PermissionRule | None:
    """Build a minimal AgentScope PermissionRule from platform policy.

    This helper is experimental and is not wired into PermissionContext yet.
    It deliberately returns None for invalid inputs instead of breaking the
    AgentScope chat path.
    """

    behavior_map: dict[str, PermissionBehavior] = {
        "allow": PermissionBehavior.ALLOW,
        "deny": PermissionBehavior.DENY,
        "ask": PermissionBehavior.ASK,
    }
    behavior = behavior_map.get(effect)
    if behavior is None or not tool_name.strip():
        return None

    try:
        return PermissionRule(
            tool_name=tool_name.strip(),
            rule_content=rule_content,
            behavior=behavior,
            source=source,
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Failed to build AgentScope PermissionRule for tool=%s.",
            tool_name,
        )
        return None


def build_agentscope_permission_rule_from_platform_rule(
    rule: dict[str, Any],
    *,
    effect: PermissionEffect = "allow",
    source: str = "agent-platform",
) -> PermissionRule | None:
    tool_name = rule.get("tool_name")
    if not isinstance(tool_name, str):
        return None
    return build_agentscope_permission_rule_for_tool(
        tool_name,
        effect=effect,
        rule_content=None,
        source=source,
    )
