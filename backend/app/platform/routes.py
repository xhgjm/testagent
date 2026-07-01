from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.config import Settings, get_settings
from backend.app.platform.native_client import (
    AgentScopeNativeClient,
    extract_collection,
    extract_resource_id,
)
from backend.app.platform.audit import (
    append_tool_audit_record,
    read_tool_audit_records,
)
from backend.app.platform.permissions import is_tool_allowed
from backend.app.platform.schemas import (
    AgentCreateRequest,
    AgentCreateResponse,
    AgentListResponse,
    ChatRequest,
    CredentialCreateRequest,
    CredentialCreateResponse,
    PlatformOverviewResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    StreamUrlResponse,
    ToolAuditListResponse,
    ToolInfo,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolListResponse,
    WorkspaceResolveResponse,
)
from backend.app.platform.security import ScopedUser, get_scoped_user
from backend.app.platform.tools import get_registered_tool, list_registered_tools
from backend.app.platform.workspace import ensure_workspace_path


router = APIRouter(prefix="/api/platform", tags=["platform-api"])


def get_native_client(settings: Settings = Depends(get_settings)) -> AgentScopeNativeClient:
    return AgentScopeNativeClient(settings)


@router.get("/overview", response_model=PlatformOverviewResponse)
async def platform_overview() -> PlatformOverviewResponse:
    return PlatformOverviewResponse(
        platform="agent-platform",
        phase="phase-2",
        agent_service="agentscope",
        features={
            "tenant_isolation": True,
            "user_isolation": True,
            "credential_management": True,
            "agent_management": True,
            "session_management": True,
            "chat": True,
            "message_history": True,
            "sse": "native stream url",
            "workspace": True,
            "tools": True,
            "permission": True,
            "tool_audit": True,
            "rag": "reserved for phase-3",
            "memory": "reserved for phase-4",
            "agent_team": "reserved for phase-5",
        },
    )


@router.post("/credentials", response_model=CredentialCreateResponse)
async def create_platform_credential(
    request: CredentialCreateRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    native_client: AgentScopeNativeClient = Depends(get_native_client),
) -> CredentialCreateResponse:
    if request.provider != "openai_compatible":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phase 1.5 only supports provider=openai_compatible.",
        )

    payload = {
        "data": {
            "type": "openai_credential",
            "name": request.name,
            "api_key": request.api_key,
            "base_url": request.base_url,
        },
    }
    native_response = await native_client.create_credential(scoped_user, payload)
    return CredentialCreateResponse(
        credential_id=extract_resource_id(native_response, "credential_id", "id"),
        provider=request.provider,
        name=request.name,
    )


@router.post("/agents", response_model=AgentCreateResponse)
async def create_platform_agent(
    request: AgentCreateRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    native_client: AgentScopeNativeClient = Depends(get_native_client),
) -> AgentCreateResponse:
    payload = {
        "name": request.name,
        "system_prompt": request.system_prompt,
    }
    native_response = await native_client.create_agent(scoped_user, payload)
    return AgentCreateResponse(
        agent_id=extract_resource_id(native_response, "agent_id", "id"),
        name=request.name,
    )


@router.get("/agents", response_model=AgentListResponse)
async def list_platform_agents(
    scoped_user: ScopedUser = Depends(get_scoped_user),
    native_client: AgentScopeNativeClient = Depends(get_native_client),
) -> AgentListResponse:
    native_response = await native_client.list_agents(scoped_user)
    agents, _ = extract_collection(native_response, "agents")
    return AgentListResponse(agents=agents)


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_platform_session(
    request: SessionCreateRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    native_client: AgentScopeNativeClient = Depends(get_native_client),
) -> SessionCreateResponse:
    payload = {
        "agent_id": request.agent_id,
        "name": request.name,
        "chat_model_config": {
            "type": request.model_type,
            "credential_id": request.credential_id,
            "model": request.model,
            "parameters": {
                "temperature": request.temperature,
            },
        },
    }
    native_response = await native_client.create_session(scoped_user, payload)
    return SessionCreateResponse(
        session_id=extract_resource_id(native_response, "session_id", "id"),
        agent_id=request.agent_id,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_platform_sessions(
    agent_id: str = Query(...),
    scoped_user: ScopedUser = Depends(get_scoped_user),
    native_client: AgentScopeNativeClient = Depends(get_native_client),
) -> SessionListResponse:
    native_response = await native_client.list_sessions(scoped_user, agent_id)
    sessions, total = extract_collection(native_response, "sessions")
    return SessionListResponse(sessions=sessions, total=total)


@router.post("/chat")
async def post_platform_chat(
    request: ChatRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    native_client: AgentScopeNativeClient = Depends(get_native_client),
) -> Any:
    payload = {
        "agent_id": request.agent_id,
        "session_id": request.session_id,
        "input": {
            "name": "user",
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": request.message,
                },
            ],
        },
    }
    return await native_client.post_chat(scoped_user, payload)


@router.get("/sessions/{session_id}/messages")
async def get_platform_messages(
    session_id: str,
    agent_id: str = Query(...),
    scoped_user: ScopedUser = Depends(get_scoped_user),
    native_client: AgentScopeNativeClient = Depends(get_native_client),
) -> Any:
    return await native_client.get_messages(scoped_user, session_id, agent_id)


@router.get(
    "/sessions/{session_id}/stream-url",
    response_model=StreamUrlResponse,
)
async def get_platform_stream_url(
    session_id: str,
    agent_id: str = Query(...),
    scoped_user: ScopedUser = Depends(get_scoped_user),
) -> StreamUrlResponse:
    _ = scoped_user
    safe_session_id = quote(session_id, safe="")
    safe_agent_id = quote(agent_id, safe="")
    return StreamUrlResponse(
        stream_url=f"/sessions/{safe_session_id}/stream?agent_id={safe_agent_id}",
        note=(
            "Use the native AgentScope SSE endpoint with the same X-Tenant-ID "
            "and X-User-ID headers. Platform SSE proxy will be implemented in "
            "a later phase."
        ),
    )


@router.get("/workspaces/resolve", response_model=WorkspaceResolveResponse)
async def resolve_platform_workspace(
    agent_id: str = Query(...),
    session_id: str = Query(...),
    create: bool = Query(default=True),
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> WorkspaceResolveResponse:
    path, created = ensure_workspace_path(
        settings,
        scoped_user,
        agent_id,
        session_id,
        create=create,
    )
    return WorkspaceResolveResponse(
        tenant_id=scoped_user.tenant_id,
        user_id=scoped_user.user_id,
        agent_id=agent_id,
        session_id=session_id,
        workspace_path=str(path),
        created=created,
        exists=path.exists(),
        isolation_strategy="tenant_id/user_id/agent_id/session_id",
    )


@router.get("/tools", response_model=ToolListResponse)
async def list_platform_tools(
    scoped_user: ScopedUser = Depends(get_scoped_user),
) -> ToolListResponse:
    _ = scoped_user
    tools = [
        ToolInfo(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
        )
        for tool in list_registered_tools()
    ]
    return ToolListResponse(
        tools=tools,
        permission_model="default_deny_explicit_allow",
    )


@router.post("/tools/{tool_name}/invoke", response_model=ToolInvokeResponse)
async def invoke_platform_tool(
    tool_name: str,
    request: ToolInvokeRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> ToolInvokeResponse:
    tool = get_registered_tool(tool_name)
    if tool is None:
        append_tool_audit_record(
            settings,
            scoped_user,
            request.agent_id,
            request.session_id,
            tool_name,
            allowed=False,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_name}",
        )

    allowed = is_tool_allowed(settings, scoped_user, request.agent_id, tool_name)
    append_tool_audit_record(
        settings,
        scoped_user,
        request.agent_id,
        request.session_id,
        tool_name,
        allowed=allowed,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tool invocation denied. Phase 2 uses default deny; add an "
                "explicit allow rule to PLATFORM_TOOL_PERMISSION_FILE."
            ),
        )

    result = await tool.handler(request.arguments)
    return ToolInvokeResponse(tool_name=tool_name, allowed=True, result=result)


@router.get("/audit/tool-calls", response_model=ToolAuditListResponse)
async def list_tool_call_audit(
    agent_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> ToolAuditListResponse:
    records = read_tool_audit_records(
        settings,
        scoped_user,
        agent_id=agent_id,
        session_id=session_id,
        tool_name=tool_name,
        limit=limit,
    )
    return ToolAuditListResponse(records=records, total=len(records))
