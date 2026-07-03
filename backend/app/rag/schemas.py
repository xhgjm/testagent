from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeBaseCreateRequest(BaseModel):
    """Platform-only KnowledgeBase metadata create request."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("name must not be empty")
        return name

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip()


class KnowledgeBaseResponse(BaseModel):
    kb_id: str
    tenant_id: str
    owner_user_id: str
    scoped_user_id: str
    name: str
    description: str
    status: Literal["active", "deleted"]
    runtime_enabled: bool
    native_kb_id: str | None = None
    native_collection: str | None = None
    isolation_strategy: str
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse]
    total: int


class KnowledgeBaseDeleteResponse(BaseModel):
    kb_id: str
    deleted: bool
    status: Literal["deleted"]


class DocumentCreateRequest(BaseModel):
    """Platform-only Document metadata create request."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    source_type: Literal["file"] = "file"
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("name must not be empty")
        return name

    @field_validator("content_type")
    @classmethod
    def strip_content_type(cls, value: str) -> str:
        content_type = value.strip()
        if not content_type:
            raise ValueError("content_type must not be empty")
        return content_type


class DocumentResponse(BaseModel):
    document_id: str
    knowledge_base_id: str
    tenant_id: str
    owner_user_id: str
    created_by: str
    name: str
    source_type: Literal["file"]
    content_type: str
    size_bytes: int
    status: Literal["registered", "uploaded", "parsing", "parsed", "failed", "deleted"]
    runtime_enabled: bool
    native_document_id: str | None = None
    checksum_sha256: str | None = None
    parser_name: str | None = None
    chunker_name: str | None = None
    chunk_count: int = 0
    uploaded_at: str | None = None
    parsed_at: str | None = None
    error_code: str | None = None
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class DocumentDeleteResponse(BaseModel):
    document_id: str
    knowledge_base_id: str
    deleted: bool
    status: Literal["deleted"]
