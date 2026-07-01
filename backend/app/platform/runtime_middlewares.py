import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from agentscope.middleware import MiddlewareBase

from backend.app.config import Settings, get_settings


logger = logging.getLogger(__name__)

RUNTIME_AUDIT_MIDDLEWARE_MODES = {"runtime_echo", "mock"}


class RuntimeToolAuditMiddleware(MiddlewareBase):
    """Minimal pass-through runtime middleware for future tool audit expansion."""

    def __init__(self, user_id: str, agent_id: str, session_id: str) -> None:
        self.user_id = user_id
        self.agent_id = agent_id
        self.session_id = session_id

    async def on_acting(
        self,
        agent: Any,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        """Pass through tool execution.

        Phase 2.3.5 writes concrete runtime_echo_tool audit records in the
        callable wrapper. This skeleton verifies the AgentScope middleware
        integration point without depending on every tool event shape.
        """

        _ = (agent, input_kwargs)
        async for event in next_handler():
            yield event


async def build_extra_agent_middlewares(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[MiddlewareBase]:
    try:
        return _build_extra_agent_middlewares(
            get_settings(),
            user_id,
            agent_id,
            session_id,
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Runtime middleware factory failed; returning no middleware.",
        )
        return []


def _build_extra_agent_middlewares(
    settings: Settings,
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[MiddlewareBase]:
    if not settings.platform_enable_runtime_audit:
        return []

    mode = settings.platform_runtime_audit_mode.strip().lower()
    if mode == "disabled":
        return []

    if mode not in RUNTIME_AUDIT_MIDDLEWARE_MODES:
        logger.warning(
            "Unsupported PLATFORM_RUNTIME_AUDIT_MODE=%s; returning no middleware.",
            settings.platform_runtime_audit_mode,
        )
        return []

    return [RuntimeToolAuditMiddleware(user_id, agent_id, session_id)]
