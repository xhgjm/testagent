from agentscope.middleware import MiddlewareBase

from backend.app.platform.runtime_middlewares import (
    build_extra_agent_middlewares as build_platform_runtime_middlewares,
)


async def build_extra_agent_middlewares(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[MiddlewareBase]:
    """Build tenant-aware AgentScope middleware instances.

    Delegates to the platform runtime middleware factory. It returns [] by
    default unless runtime audit is explicitly enabled. Planned middleware:
    - TracingMiddleware
    - BudgetControlMiddleware
    - TenantContextMiddleware
    - ToolAuditMiddleware
    - RAGMiddleware
    - Mem0LongTermMemoryMiddleware
    """

    return await build_platform_runtime_middlewares(user_id, agent_id, session_id)
