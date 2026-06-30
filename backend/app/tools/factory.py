async def build_extra_agent_tools(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list:
    """Build tenant-aware tools for an AgentScope agent session.

    First-stage MVP returns no tools. Later versions should inject tools by
    tenant, user_id, agent_id, and session_id.

    Examples:
    - CRM read-only lookup tool
    - Ticketing system tool
    - Database read-only query tool with row-level permission checks
    - RAG retrieval tool bound to tenant knowledge bases
    - Workspace file inspection tool
    """

    _ = (user_id, agent_id, session_id)
    # TODO: Resolve tenant_id from user/session context and inject tools by
    # tenant_id + user_id + agent_id + session_id.
    # TODO: Return AgentScope-compatible tool instances after enterprise
    # permission and audit policies are in place.
    return []
