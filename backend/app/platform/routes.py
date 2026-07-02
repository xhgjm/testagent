import asyncio
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from urllib.parse import quote
from uuid import uuid4

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
from backend.app.platform.permissions import (
    add_scoped_permission_rule,
    delete_scoped_permission_rule,
    is_tool_allowed,
    list_scoped_permission_rules,
)
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
    ToolPermissionCreateRequest,
    ToolPermissionListResponse,
    ToolPermissionRule,
    WorkspaceCleanupRequest,
    WorkspaceCleanupResponse,
    WorkspaceResolveResponse,
    WorkspaceFileInfo,
    WorkspaceFileListResponse,
)
from backend.app.platform.security import ScopedUser, get_scoped_user
from backend.app.platform.tools import get_registered_tool, list_registered_tools
from backend.app.platform.workspace import (
    cleanup_workspace_candidates,
    ensure_workspace_path,
    list_workspace_files,
)
from backend.app.rag.config import build_rag_service_plan


router = APIRouter(prefix="/api/platform", tags=["platform-api"])


def get_native_client(settings: Settings = Depends(get_settings)) -> AgentScopeNativeClient:
    return AgentScopeNativeClient(settings)


@router.get("/overview", response_model=PlatformOverviewResponse)
async def platform_overview(
    settings: Settings = Depends(get_settings),
) -> PlatformOverviewResponse:
    rag_plan = build_rag_service_plan(settings)
    return PlatformOverviewResponse(
        platform="agent-platform",
        phase="phase-3.2",
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
            "tool_permission_admin": True,
            "tool_timeout": True,
            "structured_tracing": True,
            "tool_native_metadata": True,
            "workspace_files": True,
            "workspace_cleanup": "dry-run by default",
            "rag": rag_plan.model_dump(),
            "rag_config_skeleton": True,
            "rag_requested_enabled": rag_plan.requested_enabled,
            "rag_effective_enabled": rag_plan.effective_enabled,
            "rag_mode": rag_plan.mode,
            "rag_native_base_url_configured": (
                rag_plan.native_base_url_configured
            ),
            "rag_runtime_registered": rag_plan.runtime_registered,
            "rag_isolation_strategy": rag_plan.isolation_strategy,
            "rag_index_worker_requested": rag_plan.index_worker_requested,
            "rag_status": rag_plan.status,
            "rag_issues": list(rag_plan.issues),
            "knowledge_base_facade_registered": True,
            "knowledge_base_metadata_registry": True,
            "knowledge_base_registry": "local_json_metadata_only",
            "knowledge_base_facade": "metadata_only_owner_private",
            "knowledge_base_runtime_enabled": False,
            "knowledge_base_runtime_connected": False,
            "knowledge_base_native_calls": False,
            "knowledge_base_native_api_called": False,
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


@router.get("/workspaces/files", response_model=WorkspaceFileListResponse)
async def list_platform_workspace_files(
    agent_id: str = Query(...),
    session_id: str = Query(...),
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> WorkspaceFileListResponse:
    workspace, files = list_workspace_files(
        settings,
        scoped_user,
        agent_id,
        session_id,
    )
    return WorkspaceFileListResponse(
        workspace_path=str(workspace),
        files=[WorkspaceFileInfo(**item) for item in files],
        total=len(files),
    )


@router.post(
    "/workspaces/cleanup-preview",
    response_model=WorkspaceCleanupResponse,
)
async def preview_workspace_cleanup(
    request: WorkspaceCleanupRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> WorkspaceCleanupResponse:
    workspace, candidates, _ = cleanup_workspace_candidates(
        settings,
        scoped_user,
        request.agent_id,
        request.session_id,
        request.max_age_days,
        dry_run=True,
    )
    return WorkspaceCleanupResponse(
        workspace_path=str(workspace),
        dry_run=True,
        candidates=candidates,
        total=len(candidates),
        deleted=0,
    )


@router.post("/workspaces/cleanup", response_model=WorkspaceCleanupResponse)
async def cleanup_workspace(
    request: WorkspaceCleanupRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> WorkspaceCleanupResponse:
    workspace, candidates, deleted = cleanup_workspace_candidates(
        settings,
        scoped_user,
        request.agent_id,
        request.session_id,
        request.max_age_days,
        dry_run=request.dry_run,
    )
    return WorkspaceCleanupResponse(
        workspace_path=str(workspace),
        dry_run=request.dry_run,
        candidates=candidates,
        total=len(candidates),
        deleted=deleted,
    )


@router.get("/tools", response_model=ToolListResponse)
async def list_platform_tools(
    scoped_user: ScopedUser = Depends(get_scoped_user),
) -> ToolListResponse:
    _ = scoped_user
    tools = [
        ToolInfo(
            tool_name=tool.name,
            name=tool.name,
            description=tool.description,
            native_type=tool.native_type,
            native_ref=tool.native_ref,
            timeout_seconds=tool.timeout_seconds,
            enabled=tool.enabled,
            input_schema=tool.input_schema,
            default_timeout_seconds=tool.default_timeout_seconds,
        )
        for tool in list_registered_tools()
    ]
    return ToolListResponse(
        tools=tools,
        permission_model="default_deny_explicit_allow",
    )


@router.get("/tool-permissions", response_model=ToolPermissionListResponse)
async def list_tool_permissions(
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> ToolPermissionListResponse:
    rules = [
        ToolPermissionRule(**rule)
        for rule in list_scoped_permission_rules(settings, scoped_user)
    ]
    return ToolPermissionListResponse(rules=rules, total=len(rules))


@router.post("/tool-permissions", response_model=ToolPermissionRule)
async def create_tool_permission(
    request: ToolPermissionCreateRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> ToolPermissionRule:
    try:
        rule = add_scoped_permission_rule(
            settings,
            scoped_user,
            request.agent_id,
            request.tool_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ToolPermissionRule(**rule)


@router.delete("/tool-permissions/{rule_id}")
async def delete_tool_permission(
    rule_id: str,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        removed = delete_scoped_permission_rule(settings, scoped_user, rule_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission rule not found for current tenant/user.",
        )
    return {"deleted": True, "rule_id": rule_id}


@router.post("/tools/{tool_name}/invoke", response_model=ToolInvokeResponse)
async def invoke_platform_tool(
    tool_name: str,
    request: ToolInvokeRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> ToolInvokeResponse:
    trace_id = uuid4().hex
    started_at = datetime.now(UTC).isoformat()
    started = perf_counter()

    def finish_record(
        *,
        allowed: bool,
        trace_status: str,
        error_code: str | None = None,
    ) -> tuple[str, int]:
        finished_at = datetime.now(UTC).isoformat()
        duration_ms = int((perf_counter() - started) * 1000)
        append_tool_audit_record(
            settings,
            scoped_user,
            request.agent_id,
            request.session_id,
            tool_name,
            allowed=allowed,
            trace_id=trace_id,
            status=trace_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error_code=error_code,
        )
        return finished_at, duration_ms

    tool = get_registered_tool(tool_name)
    if tool is None:
        _, duration_ms = finish_record(
            allowed=False,
            trace_status="not_found",
            error_code="TOOL_NOT_FOUND",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "TOOL_NOT_FOUND",
                "message": f"Tool not found: {tool_name}",
                "trace_id": trace_id,
                "duration_ms": duration_ms,
            },
        )

    allowed = is_tool_allowed(settings, scoped_user, request.agent_id, tool_name)
    if not allowed:
        _, duration_ms = finish_record(
            allowed=False,
            trace_status="denied",
            error_code="PERMISSION_DENIED",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "PERMISSION_DENIED",
                "message": (
                    "Tool invocation denied. Tool permission uses default deny; "
                    "add an explicit allow rule."
                ),
                "trace_id": trace_id,
                "duration_ms": duration_ms,
            },
        )

    timeout_seconds = request.timeout_seconds or tool.default_timeout_seconds
    try:
        result = await asyncio.wait_for(
            tool.handler(request.arguments),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        _, duration_ms = finish_record(
            allowed=True,
            trace_status="timeout",
            error_code="TOOL_TIMEOUT",
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error_code": "TOOL_TIMEOUT",
                "message": f"Tool timed out after {timeout_seconds} seconds.",
                "trace_id": trace_id,
                "duration_ms": duration_ms,
            },
        ) from exc
    except Exception as exc:
        _, duration_ms = finish_record(
            allowed=True,
            trace_status="error",
            error_code="TOOL_ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "TOOL_ERROR",
                "message": "Tool execution failed.",
                "trace_id": trace_id,
                "duration_ms": duration_ms,
            },
        ) from exc

    _, duration_ms = finish_record(allowed=True, trace_status="success")
    return ToolInvokeResponse(
        tool_name=tool_name,
        allowed=True,
        trace_id=trace_id,
        status="success",
        duration_ms=duration_ms,
        result=result,
    )


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
