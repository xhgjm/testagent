from backend.app.platform_context import PlatformContext


def build_extra_agent_middlewares(context: PlatformContext) -> list[object]:
    """Build tenant-aware AgentScope middleware instances.

    First-stage MVP returns no middleware. Planned middleware:
    - TracingMiddleware
    - BudgetControlMiddleware
    - TenantContextMiddleware
    - ToolAuditMiddleware
    - RAGMiddleware
    - Mem0LongTermMemoryMiddleware
    """

    _ = context
    # TODO: Confirm AgentScope 2.0.3 middleware interface before returning instances.
    return []
