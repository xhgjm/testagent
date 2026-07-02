from pydantic import BaseModel

from backend.app.config import Settings


ALLOWED_RAG_MODES = {"disabled", "native_service"}
ALLOWED_ISOLATION_STRATEGIES = {
    "collection_per_kb",
    "shared_collection_metadata_filter",
}


class RagConfigStatus(BaseModel):
    """Safe Phase 3.1 RAG configuration status.

    `effective_enabled` means the real RAG runtime is wired into AgentScope.
    It stays false in Phase 3.1 even when PLATFORM_ENABLE_RAG is true.
    """

    requested_enabled: bool = False
    effective_enabled: bool = False
    mode: str = "disabled"
    native_base_url_configured: bool = False
    isolation_strategy: str = "collection_per_kb"
    index_worker_requested: bool = False
    runtime_registered: bool = False
    status: str = "disabled"
    issues: tuple[str, ...] = ()
    # Backward-compatible fields for existing capability views.
    enabled: bool = False
    mode_valid: bool = True
    isolation_strategy_valid: bool = True
    index_worker_enabled: bool = False
    knowledge_base_manager_enabled: bool = False
    blob_store_enabled: bool = False
    vector_store_enabled: bool = False
    notes: list[str]


RagServicePlan = RagConfigStatus


def resolve_rag_config_status(settings: Settings) -> RagConfigStatus:
    """Describe Phase 3.1 RAG config without wiring a real runtime.

    This function must be safe for `/api/platform/overview` and app startup:
    it validates configuration shape, reports status, and never constructs
    AgentScope RAG objects, vector stores, blob stores, or index workers.
    """

    mode = settings.platform_rag_mode.strip().lower() or "disabled"
    isolation_strategy = (
        settings.platform_rag_isolation_strategy.strip().lower()
        or "collection_per_kb"
    )
    mode_valid = mode in ALLOWED_RAG_MODES
    isolation_valid = isolation_strategy in ALLOWED_ISOLATION_STRATEGIES
    requested_enabled = settings.platform_enable_rag
    native_base_url_configured = bool(
        settings.platform_rag_native_base_url.strip(),
    )
    issues: list[str] = []

    if not mode_valid:
        issues.append(
            "PLATFORM_RAG_MODE must be disabled or native_service.",
        )
    if not isolation_valid:
        issues.append(
            "PLATFORM_RAG_ISOLATION_STRATEGY must be collection_per_kb or shared_collection_metadata_filter.",
        )
    if settings.platform_rag_enable_index_worker:
        issues.append(
            "PLATFORM_RAG_ENABLE_INDEX_WORKER=true is rejected in Phase 3.1; index worker is not implemented.",
        )
    if requested_enabled and mode == "disabled":
        issues.append(
            "PLATFORM_ENABLE_RAG=true requires PLATFORM_RAG_MODE=native_service.",
        )
    if requested_enabled and mode == "native_service" and not native_base_url_configured:
        issues.append(
            "PLATFORM_RAG_NATIVE_BASE_URL is required when RAG is requested in native_service mode.",
        )

    if not requested_enabled:
        status = "disabled"
        # Disabled mode should not be reported as misconfigured because users
        # may keep future-looking values in .env while RAG is off.
        issues = []
    elif issues:
        status = "misconfigured"
    else:
        status = "configured_not_implemented"

    return RagConfigStatus(
        requested_enabled=requested_enabled,
        effective_enabled=False,
        mode=mode,
        native_base_url_configured=native_base_url_configured,
        isolation_strategy=isolation_strategy if isolation_valid else "collection_per_kb",
        index_worker_requested=settings.platform_rag_enable_index_worker,
        runtime_registered=False,
        status=status,
        issues=tuple(issues),
        enabled=False,
        mode_valid=mode_valid,
        isolation_strategy_valid=isolation_valid,
        index_worker_enabled=False,
        knowledge_base_manager_enabled=False,
        blob_store_enabled=False,
        vector_store_enabled=False,
        notes=[
            "RAG is a platform capability, not the whole application.",
            "Knowledge bases must be isolated by tenant_id and permission policy.",
            "Phase 3.1 only parses RAG config; it does not enable runtime RAG.",
            "KnowledgeBase CRUD, document upload, search, and chat RAG are not implemented yet.",
        ],
    )


def build_rag_service_plan(settings: Settings) -> RagConfigStatus:
    """Backward-compatible wrapper used by existing capability views."""

    return resolve_rag_config_status(settings)
