from backend.app.platform_context import PlatformContext


def build_extra_agent_tools(context: PlatformContext) -> list[object]:
    """Build tenant-aware tools for an AgentScope agent.

    First-stage MVP returns no tools. Later versions should inject tools by
    tenant_id, user_id, agent_id, and session_id.

    Examples:
    - CRM read-only lookup tool
    - Ticketing system tool
    - Database read-only query tool with row-level permission checks
    - RAG retrieval tool bound to tenant knowledge bases
    - Workspace file inspection tool
    """

    _ = context
    # TODO: Confirm AgentScope 2.0.3 tool interface before returning concrete tools.
    return []
