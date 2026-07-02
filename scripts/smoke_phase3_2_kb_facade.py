import json
import shutil
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import Settings, get_settings
from backend.app.platform.routes import router as platform_router
from backend.app.platform.security import ScopedUser
from backend.app.rag import registry as registry_module
from backend.app.rag.registry import KnowledgeBaseRegistry
from backend.app.rag.routes import router as rag_router
from backend.app.rag.schemas import KnowledgeBaseCreateRequest


TEMP_ROOT = PROJECT_ROOT / ".cache" / "phase3_2_kb_facade_smoke"
REGISTRY_PATH = TEMP_ROOT / "knowledge-bases.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_client() -> TestClient:
    if TEMP_ROOT.exists():
        shutil.rmtree(TEMP_ROOT)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        platform_rag_kb_registry_path=str(REGISTRY_PATH),
        platform_enable_rag=False,
        platform_rag_mode="disabled",
        platform_rag_enable_index_worker=False,
    )
    app = FastAPI()
    app.include_router(platform_router)
    app.include_router(rag_router)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def assert_python_version() -> None:
    assert_true(
        sys.version_info >= (3, 11),
        f"Phase 3.2 smoke must run on Python 3.11+, got {sys.version}.",
    )


def assert_main_rag_runtime_disabled() -> None:
    main_source = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(
        encoding="utf-8",
    )
    for needle in (
        "knowledge_base_manager=None",
        "knowledge_parsers=None",
        "knowledge_chunker=None",
        "blob_store=None",
        "enable_index_worker=False",
    ):
        assert_true(needle in main_source, f"main.py must keep {needle}.")
    assert_true(
        "enable_index_worker=settings.platform_rag_enable_index_worker"
        not in main_source,
        "Phase 3.2 must not bind index worker to PLATFORM_RAG_ENABLE_INDEX_WORKER.",
    )


def assert_facade_does_not_call_native_rag() -> None:
    rag_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            PROJECT_ROOT / "backend" / "app" / "rag" / "routes.py",
            PROJECT_ROOT / "backend" / "app" / "rag" / "registry.py",
        )
    )
    forbidden = (
        "AgentScopeNativeClient",
        "/knowledge_bases",
        "CollectionPerKbManager",
        "QdrantStore",
        "Embedding",
    )
    for needle in forbidden:
        assert_true(
            needle not in rag_sources,
            f"Phase 3.2 KB facade must not call or construct {needle}.",
        )


def assert_platform_routes(openapi_paths: dict[str, Any]) -> None:
    route_methods = {
        path: {method.upper() for method in spec.keys()}
        for path, spec in openapi_paths.items()
        if path.startswith("/api/platform/knowledge-bases")
    }
    assert_true(
        route_methods.get("/api/platform/knowledge-bases") == {"GET", "POST"},
        "Platform KB collection route must have exactly GET and POST.",
    )
    assert_true(
        route_methods.get("/api/platform/knowledge-bases/{kb_id}") == {
            "DELETE",
            "GET",
        },
        "Platform KB item route must have exactly GET and DELETE.",
    )
    for path, methods in route_methods.items():
        if path.startswith("/api/platform/knowledge-bases"):
            assert_true("PUT" not in methods, "Phase 3.2 must not expose PUT.")
            assert_true("PATCH" not in methods, "Phase 3.2 must not expose PATCH.")
            assert_true("documents" not in path, "Phase 3.2 must not expose documents.")
            assert_true("search" not in path, "Phase 3.2 must not expose search.")


def assert_atomic_replace_behavior() -> None:
    registry = KnowledgeBaseRegistry()
    settings = Settings(
        platform_rag_kb_registry_path=str(TEMP_ROOT / "atomic" / "kb.json"),
    )
    user = ScopedUser(
        tenant_id="tenantAtomic",
        user_id="userAtomic",
        scoped_user_id="tenantAtomic:userAtomic",
    )
    request = KnowledgeBaseCreateRequest(name="atomic")
    real_replace = registry_module.os.replace
    calls: list[tuple[Path, Path]] = []

    def capture_replace(src: Any, dst: Any) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        calls.append((src_path, dst_path))
        assert_true(
            src_path.parent == dst_path.parent,
            "Atomic temp file must be in the target directory.",
        )
        assert_true(
            src_path.name.endswith(".tmp"),
            "Atomic temp file name should be clearly temporary.",
        )
        real_replace(src, dst)

    registry_module.os.replace = capture_replace
    try:
        registry.create(settings, user, request)
    finally:
        registry_module.os.replace = real_replace

    assert_true(len(calls) == 1, "Registry write must call os.replace once.")


def main() -> None:
    assert_python_version()
    assert_main_rag_runtime_disabled()
    assert_facade_does_not_call_native_rag()
    client = build_client()
    assert_atomic_replace_behavior()

    openapi_paths = client.get("/openapi.json").json()["paths"]
    assert_platform_routes(openapi_paths)
    assert_true(
        "/api/platform/knowledge-bases" in openapi_paths,
        "Platform KnowledgeBase list/create route must be registered.",
    )
    assert_true(
        "/api/platform/knowledge-bases/{kb_id}" in openapi_paths,
        "Platform KnowledgeBase detail/delete route must be registered.",
    )

    overview = client.get("/api/platform/overview").json()
    overview_payload = json.dumps(overview, ensure_ascii=False)
    assert_true(overview["phase"] == "phase-3.2", "Overview phase must be phase-3.2.")
    assert_true(
        overview["features"]["knowledge_base_facade_registered"] is True,
        "Overview should expose KB facade registration state.",
    )
    assert_true(
        overview["features"]["knowledge_base_registry"]
        == "local_json_metadata_only",
        "Overview should report local JSON metadata registry.",
    )
    assert_true(
        overview["features"]["knowledge_base_runtime_connected"] is False,
        "KB facade must not connect RAG runtime.",
    )
    assert_true(
        overview["features"]["knowledge_base_native_api_called"] is False,
        "KB facade must not call native RAG API.",
    )
    assert_true(
        overview["features"]["rag_effective_enabled"] is False,
        "KB facade must not enable RAG runtime.",
    )
    assert_true(
        overview["features"]["rag_runtime_registered"] is False,
        "KB facade must not register native RAG runtime.",
    )
    assert_true(
        str(REGISTRY_PATH) not in overview_payload,
        "Overview must not expose registry path.",
    )

    headers_a = {"X-Tenant-ID": "tenantA", "X-User-ID": "userA"}
    headers_b_same_tenant = {"X-Tenant-ID": "tenantA", "X-User-ID": "userB"}
    headers_b_tenant = {"X-Tenant-ID": "tenantB", "X-User-ID": "userA"}

    list_empty = client.get("/api/platform/knowledge-bases", headers=headers_a)
    assert_true(list_empty.status_code == 200, "Empty list should return 200.")
    assert_true(list_empty.json()["total"] == 0, "Missing registry should list empty.")
    assert_true(
        not REGISTRY_PATH.exists(),
        "Read-only list must not create registry file.",
    )
    get_missing = client.get(
        "/api/platform/knowledge-bases/kb_missing",
        headers=headers_a,
    )
    assert_true(get_missing.status_code == 404, "Missing KB detail should be 404.")
    assert_true(
        not REGISTRY_PATH.exists(),
        "Read-only detail must not create registry file.",
    )

    missing_header = client.get("/api/platform/knowledge-bases")
    assert_true(missing_header.status_code == 400, "Tenant/user headers are required.")

    for field in (
        "tenant_id",
        "owner_user_id",
        "scoped_user_id",
        "kb_id",
        "status",
        "runtime_enabled",
        "native_kb_id",
        "native_collection",
        "created_at",
        "updated_at",
        "isolation_strategy",
    ):
        internal_field = client.post(
            "/api/platform/knowledge-bases",
            headers=headers_a,
            json={"name": "bad", field: "injected"},
        )
        assert_true(
            internal_field.status_code == 422,
            f"Client-supplied internal field {field} must be rejected.",
        )

    invalid_requests = (
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 101},
        {"name": "valid", "description": "x" * 1001},
    )
    for body in invalid_requests:
        invalid = client.post(
            "/api/platform/knowledge-bases",
            headers=headers_a,
            json=body,
        )
        assert_true(invalid.status_code == 422, f"Invalid body passed: {body!r}")

    created = client.post(
        "/api/platform/knowledge-bases",
        headers=headers_a,
        json={"name": "Enterprise KB", "description": "metadata only"},
    )
    assert_true(created.status_code == 201, "Create KB should return 201.")
    kb = created.json()
    kb_id = kb["kb_id"]
    assert_true(kb_id.startswith("kb_"), "kb_id must be server generated.")
    assert_true(kb["tenant_id"] == "tenantA", "tenant_id must come from headers.")
    assert_true(kb["owner_user_id"] == "userA", "owner_user_id must come from headers.")
    assert_true(kb["scoped_user_id"] == "tenantA:userA", "scoped_user_id should persist.")
    assert_true(kb["status"] == "active", "Created KB status must be active.")
    assert_true(kb["runtime_enabled"] is False, "Runtime must remain disabled.")
    assert_true(kb["native_kb_id"] is None, "Native KB id must not be set.")
    assert_true(kb["native_collection"] is None, "Native collection must not be set.")

    duplicate = client.post(
        "/api/platform/knowledge-bases",
        headers=headers_a,
        json={"name": "Enterprise KB", "description": "same name allowed"},
    )
    assert_true(
        duplicate.status_code == 201,
        "Same tenant/user duplicate KB name should be allowed.",
    )
    duplicate_kb_id = duplicate.json()["kb_id"]
    assert_true(
        duplicate_kb_id != kb_id,
        "Duplicate name should still generate a different kb_id.",
    )

    list_a = client.get("/api/platform/knowledge-bases", headers=headers_a)
    assert_true(list_a.status_code == 200, "Owner list should succeed.")
    assert_true(list_a.json()["total"] == 2, "Owner list should contain two KBs.")

    detail_a = client.get(f"/api/platform/knowledge-bases/{kb_id}", headers=headers_a)
    assert_true(detail_a.status_code == 200, "Owner detail should succeed.")

    for headers in (headers_b_same_tenant, headers_b_tenant):
        list_other = client.get("/api/platform/knowledge-bases", headers=headers)
        assert_true(list_other.status_code == 200, "Other owner list should not fail.")
        assert_true(list_other.json()["total"] == 0, "Other owner should see no KBs.")
        detail_other = client.get(
            f"/api/platform/knowledge-bases/{kb_id}",
            headers=headers,
        )
        assert_true(
            detail_other.status_code == 404,
            "Cross-owner/cross-tenant detail should return 404.",
        )
        delete_other = client.delete(
            f"/api/platform/knowledge-bases/{kb_id}",
            headers=headers,
        )
        assert_true(
            delete_other.status_code == 404,
            "Cross-owner/cross-tenant delete should return 404.",
        )

    deleted = client.delete(f"/api/platform/knowledge-bases/{kb_id}", headers=headers_a)
    assert_true(deleted.status_code == 200, "Owner delete should succeed.")
    assert_true(deleted.json()["deleted"] is True, "Delete response needs deleted=true.")
    assert_true(deleted.json()["status"] == "deleted", "Delete should be soft delete.")
    list_after_delete = client.get("/api/platform/knowledge-bases", headers=headers_a)
    assert_true(
        list_after_delete.json()["total"] == 1,
        "Soft-deleted KB should be excluded from list.",
    )
    detail_after_delete = client.get(
        f"/api/platform/knowledge-bases/{kb_id}",
        headers=headers_a,
    )
    assert_true(
        detail_after_delete.status_code == 404,
        "Soft-deleted KB detail should return 404.",
    )
    delete_again = client.delete(
        f"/api/platform/knowledge-bases/{kb_id}",
        headers=headers_a,
    )
    assert_true(delete_again.status_code == 404, "Repeated delete should return 404.")
    missing_delete = client.delete(
        "/api/platform/knowledge-bases/kb_missing",
        headers=headers_a,
    )
    assert_true(missing_delete.status_code == 404, "Missing delete should return 404.")

    registry_payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert_true(registry_payload["version"] == 1, "Registry must include version=1.")
    records = registry_payload["knowledge_bases"]
    assert_true(len(records) == 2, "Registry should keep active and deleted records.")
    deleted_record = next(item for item in records if item["kb_id"] == kb_id)
    assert_true(deleted_record["status"] == "deleted", "Registry should keep tombstone.")
    assert_true(deleted_record["deleted_at"], "Soft delete should set deleted_at.")

    for bad_payload in (
        "{ this is not json",
        json.dumps({"version": 2, "knowledge_bases": []}),
        json.dumps({"version": 1, "knowledge_bases": {}}),
        json.dumps({"version": 1, "knowledge_bases": [{"kb_id": "kb_broken"}]}),
    ):
        REGISTRY_PATH.write_text(bad_payload, encoding="utf-8")
        corrupt_response = client.get("/api/platform/knowledge-bases", headers=headers_a)
        assert_true(
            corrupt_response.status_code == 500,
            "Corrupt registry should return a safe 500.",
        )
        corrupt_payload = json.dumps(corrupt_response.json(), ensure_ascii=False)
        assert_true(
            str(REGISTRY_PATH) not in corrupt_payload,
            "Registry errors must not expose filesystem paths.",
        )
        assert_true(
            bad_payload not in corrupt_payload,
            "Registry errors must not expose raw registry content.",
        )
        assert_true(
            REGISTRY_PATH.read_text(encoding="utf-8") == bad_payload,
            "Corrupt registry must not be overwritten silently.",
        )

    shutil.rmtree(TEMP_ROOT)
    print("Phase 3.2 KnowledgeBase facade hardening smoke passed.")


if __name__ == "__main__":
    main()
