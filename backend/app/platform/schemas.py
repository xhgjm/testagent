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
