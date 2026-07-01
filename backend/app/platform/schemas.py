from typing import Any

from pydantic import BaseModel, Field


class PlatformOverviewResponse(BaseModel):
    platform: str
    phase: str
    agent_service: str
    features: dict[str, Any]


class CredentialCreateRequest(BaseModel):
    provider: str
    name: str
    api_key: str = Field(repr=False)
    base_url: str


class CredentialCreateResponse(BaseModel):
    credential_id: str | None = None
    provider: str
    name: str


class AgentCreateRequest(BaseModel):
    name: str
    system_prompt: str


class AgentCreateResponse(BaseModel):
    agent_id: str | None = None
    name: str


class AgentListResponse(BaseModel):
    agents: Any


class SessionCreateRequest(BaseModel):
    agent_id: str
    credential_id: str
    name: str
    model: str
    model_type: str = "openai_chat_model"
    temperature: float = 0.3


class SessionCreateResponse(BaseModel):
    session_id: str | None = None
    agent_id: str


class SessionListResponse(BaseModel):
    sessions: Any
    total: int | None = None


class ChatRequest(BaseModel):
    agent_id: str
    session_id: str
    message: str


class StreamUrlResponse(BaseModel):
    stream_url: str
    note: str


class WorkspaceResolveResponse(BaseModel):
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    workspace_path: str
    created: bool
    exists: bool
    isolation_strategy: str


class ToolInfo(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    default_timeout_seconds: float


class ToolListResponse(BaseModel):
    tools: list[ToolInfo]
    permission_model: str


class ToolInvokeRequest(BaseModel):
    agent_id: str
    session_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float | None = Field(default=None, gt=0, le=60)


class ToolInvokeResponse(BaseModel):
    tool_name: str
    allowed: bool
    trace_id: str
    status: str
    duration_ms: int
    error_code: str | None = None
    result: Any | None = None


class ToolAuditRecord(BaseModel):
    trace_id: str | None = None
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    tool_name: str
    allowed: bool
    timestamp: str
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    error_code: str | None = None


class ToolAuditListResponse(BaseModel):
    records: list[dict[str, Any]]
    total: int


class ToolPermissionRule(BaseModel):
    rule_id: str
    tenant_id: str
    user_id: str
    agent_id: str
    tool_name: str


class ToolPermissionCreateRequest(BaseModel):
    agent_id: str = "*"
    tool_name: str


class ToolPermissionListResponse(BaseModel):
    rules: list[ToolPermissionRule]
    total: int


class WorkspaceFileInfo(BaseModel):
    path: str
    size_bytes: int
    modified_at: str
    is_dir: bool = False


class WorkspaceFileListResponse(BaseModel):
    workspace_path: str
    files: list[WorkspaceFileInfo]
    total: int


class WorkspaceCleanupRequest(BaseModel):
    agent_id: str
    session_id: str
    max_age_days: float = Field(default=7, ge=0)
    dry_run: bool = True


class WorkspaceCleanupCandidate(BaseModel):
    path: str
    size_bytes: int
    modified_at: str
    age_days: float
    deleted: bool = False


class WorkspaceCleanupResponse(BaseModel):
    workspace_path: str
    dry_run: bool
    candidates: list[WorkspaceCleanupCandidate]
    total: int
    deleted: int = 0
