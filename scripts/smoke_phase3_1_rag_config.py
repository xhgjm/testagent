import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import Settings
from backend.app.rag.config import resolve_rag_config_status


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_not_contains_sensitive_value(plan_json: str) -> None:
    assert_true(
        "rag-service.invalid" not in plan_json,
        "RAG status must not expose PLATFORM_RAG_NATIVE_BASE_URL.",
    )
    assert_true(
        "sk-" not in plan_json.lower(),
        "RAG status must not expose secret-like values.",
    )


def main() -> None:
    main_py = PROJECT_ROOT / "backend" / "app" / "main.py"
    main_source = main_py.read_text(encoding="utf-8")
    assert_true(
        "enable_index_worker=False" in main_source,
        "Phase 3.1 main.py must pass enable_index_worker=False.",
    )
    assert_true(
        "enable_index_worker=settings.platform_rag_enable_index_worker" not in main_source,
        "Phase 3.1 must not bind enable_index_worker to PLATFORM_RAG_ENABLE_INDEX_WORKER.",
    )

    default_plan = resolve_rag_config_status(Settings())
    assert_true(
        default_plan.requested_enabled is False,
        "Default PLATFORM_ENABLE_RAG must be false.",
    )
    assert_true(
        default_plan.effective_enabled is False,
        "Default RAG runtime must be disabled.",
    )
    assert_true(default_plan.mode == "disabled", "Default RAG mode must be disabled.")
    assert_true(
        default_plan.runtime_registered is False,
        "Default RAG runtime must not be registered.",
    )
    assert_true(default_plan.status == "disabled", "Default RAG status must be disabled.")
    assert_true(
        default_plan.issues == (),
        "Default disabled RAG config should not report issues.",
    )

    configured_plan = resolve_rag_config_status(
        Settings(
            platform_enable_rag=True,
            platform_rag_mode="native_service",
            platform_rag_native_base_url="http://rag-service.invalid",
            platform_rag_isolation_strategy="collection_per_kb",
            platform_rag_enable_index_worker=False,
        ),
    )
    assert_true(
        configured_plan.effective_enabled is False,
        "Phase 3.1 must not wire real RAG runtime even when requested.",
    )
    assert_true(
        configured_plan.requested_enabled is True,
        "RAG requested_enabled should reflect PLATFORM_ENABLE_RAG.",
    )
    assert_true(
        configured_plan.native_base_url_configured is True,
        "RAG status should show whether native base URL is configured.",
    )
    assert_true(
        configured_plan.runtime_registered is False,
        "Phase 3.1 must not register RAG runtime.",
    )
    assert_true(
        configured_plan.status == "configured_not_implemented",
        "Complete native_service config should be recognized but not implemented.",
    )
    assert_true(
        configured_plan.issues == (),
        "Complete native_service config should not report config issues.",
    )
    assert_not_contains_sensitive_value(
        json.dumps(configured_plan.model_dump(), ensure_ascii=False),
    )

    missing_url_plan = resolve_rag_config_status(
        Settings(
            platform_enable_rag=True,
            platform_rag_mode="native_service",
            platform_rag_native_base_url="",
        ),
    )
    assert_true(
        missing_url_plan.status == "misconfigured",
        "Missing native base URL should be misconfigured.",
    )
    assert_true(
        missing_url_plan.effective_enabled is False,
        "Missing base URL must not enable RAG runtime.",
    )
    assert_true(missing_url_plan.issues != (), "Missing base URL needs issues.")

    invalid_mode_plan = resolve_rag_config_status(
        Settings(
            platform_enable_rag=True,
            platform_rag_mode="unexpected_mode",
            platform_rag_native_base_url="http://rag-service.invalid",
        ),
    )
    assert_true(
        invalid_mode_plan.status == "misconfigured",
        "Invalid mode should be misconfigured.",
    )
    assert_true(
        invalid_mode_plan.effective_enabled is False,
        "Invalid mode must fail closed.",
    )
    assert_true(invalid_mode_plan.mode_valid is False, "Invalid mode should be reported.")
    assert_true(invalid_mode_plan.issues != (), "Invalid mode needs issues.")

    invalid_isolation_plan = resolve_rag_config_status(
        Settings(
            platform_enable_rag=True,
            platform_rag_mode="native_service",
            platform_rag_native_base_url="http://rag-service.invalid",
            platform_rag_isolation_strategy="../tenant_escape",
        ),
    )
    assert_true(
        invalid_isolation_plan.status == "misconfigured",
        "Invalid isolation strategy should be misconfigured.",
    )
    assert_true(
        invalid_isolation_plan.effective_enabled is False,
        "Invalid isolation strategy must fail closed.",
    )
    assert_true(
        invalid_isolation_plan.isolation_strategy_valid is False,
        "Invalid isolation strategy should be reported.",
    )
    assert_true(invalid_isolation_plan.issues != (), "Invalid isolation needs issues.")

    index_worker_plan = resolve_rag_config_status(
        Settings(
            platform_enable_rag=True,
            platform_rag_mode="native_service",
            platform_rag_native_base_url="http://rag-service.invalid",
            platform_rag_enable_index_worker=True,
        ),
    )
    assert_true(
        index_worker_plan.index_worker_requested is True,
        "Index worker request should be visible.",
    )
    assert_true(
        index_worker_plan.effective_enabled is False,
        "Requested index worker must not enable RAG runtime.",
    )
    assert_true(
        index_worker_plan.runtime_registered is False,
        "Requested index worker must not register RAG runtime.",
    )
    assert_true(
        index_worker_plan.status == "misconfigured",
        "Index worker request is not supported in Phase 3.1.",
    )

    for plan in (
        default_plan,
        configured_plan,
        missing_url_plan,
        invalid_mode_plan,
        invalid_isolation_plan,
        index_worker_plan,
    ):
        payload = json.dumps(plan.model_dump(), ensure_ascii=False)
        assert_not_contains_sensitive_value(payload)
        assert_true(
            "document content" not in payload.lower(),
            "RAG status must not include document content.",
        )
        assert_true(
            plan.effective_enabled is False,
            "Phase 3.1 effective_enabled must always be false.",
        )
        assert_true(
            plan.runtime_registered is False,
            "Phase 3.1 runtime_registered must always be false.",
        )

    disabled_with_future_values = resolve_rag_config_status(
        Settings(
            platform_enable_rag=False,
            platform_rag_mode="unexpected_mode",
            platform_rag_native_base_url="http://rag-service.invalid",
            platform_rag_isolation_strategy="../tenant_escape",
        ),
    )
    assert_true(
        disabled_with_future_values.status == "disabled",
        "Disabled RAG config should stay disabled and not block startup.",
    )

    print("Phase 3.1 RAG config skeleton smoke passed.")


if __name__ == "__main__":
    main()
