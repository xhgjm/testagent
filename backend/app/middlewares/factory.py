async def build_extra_agent_middlewares(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list:
    """Build tenant-aware AgentScope middleware instances.

    First-stage MVP returns no middleware. Planned middleware:
    - TracingMiddleware
    - BudgetControlMiddleware
    - TenantContextMiddleware
    - ToolAuditMiddleware
    - RAGMiddleware
    - Mem0LongTermMemoryMiddleware
    """

    _ = (user_id, agent_id, session_id)
    # TODO: Resolve tenant_id from user/session context and inject middleware by
    # tenant_id + user_id + agent_id + session_id.
    # TODO: Return AgentScope MiddlewareBase instances after governance policies
    # are implemented.
    return []
