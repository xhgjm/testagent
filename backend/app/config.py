from functools import lru_cache
from os import getenv
from typing import Literal

from pydantic import BaseModel, Field


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is listed in requirements.
    load_dotenv = None


class Settings(BaseModel):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "agent-platform"
    app_env: str = "development"

    agent_service_host: str = "0.0.0.0"
    agent_service_port: int = 8891

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    workspace_backend: Literal["local", "docker", "e2b"] = "local"
    workspace_basedir: str = "/data/agent-platform/workspaces"
    workspace_ttl_seconds: int = 3600

    frontend_host: str = "0.0.0.0"
    frontend_port: int = 3000
    backend_base_url: str = "http://127.0.0.1:8891"
    agent_service_internal_base_url: str = "http://127.0.0.1:8891"
    platform_tool_permission_file: str = ""
    platform_tool_audit_log_file: str = "logs/tool-calls-audit.jsonl"
    platform_tool_trace_log_file: str = "logs/tool-calls-trace.jsonl"
    platform_enable_runtime_tools: bool = False
    platform_runtime_tools_mode: str = "disabled"
    platform_enable_runtime_audit: bool = False
    platform_runtime_audit_mode: str = "disabled"
    platform_enable_rag: bool = False
    platform_rag_mode: str = "disabled"
    platform_rag_native_base_url: str = ""
    platform_rag_isolation_strategy: str = "collection_per_kb"
    platform_rag_enable_index_worker: bool = False
    platform_rag_kb_registry_path: str = ".cache/agent-platform/rag-kb-registry.json"

    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333
    blob_store_root: str = "/data/agent-platform/blobs"

    dashscope_api_key: str = Field(default="", repr=False)
    deepseek_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)
    openai_base_url: str = ""

    default_provider: str = ""
    default_model: str = ""


@lru_cache
def get_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv()

    def env_bool(name: str, default: bool = False) -> bool:
        value = getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return Settings(
        app_name=getenv("APP_NAME", "agent-platform"),
        app_env=getenv("APP_ENV", "development"),
        agent_service_host=getenv("AGENT_SERVICE_HOST", "0.0.0.0"),
        agent_service_port=int(getenv("AGENT_SERVICE_PORT", "8891")),
        redis_host=getenv("REDIS_HOST", "127.0.0.1"),
        redis_port=int(getenv("REDIS_PORT", "6379")),
        redis_db=int(getenv("REDIS_DB", "0")),
        workspace_backend=getenv("WORKSPACE_BACKEND", "local"),
        workspace_basedir=getenv(
            "WORKSPACE_BASEDIR",
            "/data/agent-platform/workspaces",
        ),
        workspace_ttl_seconds=int(getenv("WORKSPACE_TTL_SECONDS", "3600")),
        frontend_host=getenv("FRONTEND_HOST", "0.0.0.0"),
        frontend_port=int(getenv("FRONTEND_PORT", "3000")),
        backend_base_url=getenv("BACKEND_BASE_URL", "http://127.0.0.1:8891"),
        agent_service_internal_base_url=getenv(
            "AGENT_SERVICE_INTERNAL_BASE_URL",
            "http://127.0.0.1:8891",
        ),
        platform_tool_permission_file=getenv("PLATFORM_TOOL_PERMISSION_FILE", ""),
        platform_tool_audit_log_file=getenv(
            "PLATFORM_TOOL_AUDIT_LOG_FILE",
            "logs/tool-calls-audit.jsonl",
        ),
        platform_tool_trace_log_file=getenv(
            "PLATFORM_TOOL_TRACE_LOG_FILE",
            "logs/tool-calls-trace.jsonl",
        ),
        platform_enable_runtime_tools=env_bool(
            "PLATFORM_ENABLE_RUNTIME_TOOLS",
            False,
        ),
        platform_runtime_tools_mode=getenv(
            "PLATFORM_RUNTIME_TOOLS_MODE",
            "disabled",
        ),
        platform_enable_runtime_audit=env_bool(
            "PLATFORM_ENABLE_RUNTIME_AUDIT",
            False,
        ),
        platform_runtime_audit_mode=getenv(
            "PLATFORM_RUNTIME_AUDIT_MODE",
            "disabled",
        ),
        platform_enable_rag=env_bool("PLATFORM_ENABLE_RAG", False),
        platform_rag_mode=getenv("PLATFORM_RAG_MODE", "disabled"),
        platform_rag_native_base_url=getenv("PLATFORM_RAG_NATIVE_BASE_URL", ""),
        platform_rag_isolation_strategy=getenv(
            "PLATFORM_RAG_ISOLATION_STRATEGY",
            "collection_per_kb",
        ),
        platform_rag_enable_index_worker=env_bool(
            "PLATFORM_RAG_ENABLE_INDEX_WORKER",
            False,
        ),
        platform_rag_kb_registry_path=getenv(
            "PLATFORM_RAG_KB_REGISTRY_PATH",
            ".cache/agent-platform/rag-kb-registry.json",
        ),
        qdrant_host=getenv("QDRANT_HOST", "127.0.0.1"),
        qdrant_port=int(getenv("QDRANT_PORT", "6333")),
        blob_store_root=getenv("BLOB_STORE_ROOT", "/data/agent-platform/blobs"),
        dashscope_api_key=getenv("DASHSCOPE_API_KEY", ""),
        deepseek_api_key=getenv("DEEPSEEK_API_KEY", ""),
        openai_api_key=getenv("OPENAI_API_KEY", ""),
        openai_base_url=getenv("OPENAI_BASE_URL", ""),
        default_provider=getenv("DEFAULT_PROVIDER", ""),
        default_model=getenv("DEFAULT_MODEL", ""),
    )
