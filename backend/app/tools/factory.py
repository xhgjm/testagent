from agentscope.tool import ToolBase

from backend.app.platform.runtime_tools import (
    build_extra_agent_tools as build_platform_runtime_tools,
)


async def build_extra_agent_tools(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    """Build tenant-aware tools for an AgentScope agent session.

    Delegates to the platform runtime adapter. The adapter is closed by
    default and returns [] unless explicitly enabled by configuration.

    Examples:
    - CRM read-only lookup tool
    - Ticketing system tool
    - Database read-only query tool with row-level permission checks
    - RAG retrieval tool bound to tenant knowledge bases
    - Workspace file inspection tool
    """

    return await build_platform_runtime_tools(user_id, agent_id, session_id)
