import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import Settings, get_settings
from backend.app.platform.routes import router as platform_router
from backend.app.rag import document_registry as document_registry_module
from backend.app.rag.document_registry import DocumentRegistry
from backend.app.rag.routes import router as rag_router
from backend.app.rag.schemas import DocumentCreateRequest
from backend.app.platform.security import ScopedUser


TEMP_ROOT = PROJECT_ROOT / ".cache" / "phase3_3_document_facade_smoke"
KB_REGISTRY_PATH = TEMP_ROOT / "knowledge-bases.json"
DOCUMENT_REGISTRY_PATH = TEMP_ROOT / "documents.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_app() -> FastAPI:
    if TEMP_ROOT.exists():
        shutil.rmtree(TEMP_ROOT)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        platform_rag_kb_registry_path=str(KB_REGISTRY_PATH),
        platform_rag_document_registry_path=str(DOCUMENT_REGISTRY_PATH),
        platform_enable_rag=False,
        platform_rag_mode="disabled",
        platform_rag_enable_index_worker=False,
    )
    app = FastAPI()
    app.include_router(platform_router)
    app.include_router(rag_router)
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def assert_python_version() -> None:
    assert_true(
        sys.version_info >= (3, 11),
        f"Phase 3.3 smoke must run on Python 3.11+, got {sys.version}.",
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
        "Phase 3.3 must not bind index worker to PLATFORM_RAG_ENABLE_INDEX_WORKER.",
    )


def assert_facade_does_not_call_native_rag() -> None:
    rag_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            PROJECT_ROOT / "backend" / "app" / "rag" / "routes.py",
            PROJECT_ROOT / "backend" / "app" / "rag" / "document_registry.py",
        )
    )
    forbidden = (
        "AgentScopeNativeClient",
        "/knowledge_bases",
        "CollectionPerKbManager",
        "QdrantStore",
        "Embedding",
        "BlobStore",
        "multipart",
    )
    for needle in forbidden:
        assert_true(
            needle not in rag_sources,
            f"Phase 3.3 Document facade must not call or construct {needle}.",
        )


def assert_document_routes(openapi_paths: dict[str, Any]) -> None:
    collection = "/api/platform/knowledge-bases/{kb_id}/documents"
    item = "/api/platform/knowledge-bases/{kb_id}/documents/{document_id}"
    route_methods = {
        path: {method.upper() for method in spec.keys()}
        for path, spec in openapi_paths.items()
        if "/documents" in path
    }
    assert_true(
        route_methods.get(collection) == {"GET", "POST"},
        "Document collection route must have exactly GET and POST.",
    )
    assert_true(
        route_methods.get(item) == {"DELETE", "GET"},
        "Document item route must have exactly GET and DELETE.",
    )
    for path, methods in route_methods.items():
        assert_true("PUT" not in methods, "Phase 3.3 must not expose PUT.")
        assert_true("PATCH" not in methods, "Phase 3.3 must not expose PATCH.")
        assert_true("chunks" not in path, "Phase 3.3 must not expose chunks.")
        assert_true("search" not in path, "Phase 3.3 must not expose search.")


def assert_atomic_replace_behavior() -> None:
    registry = DocumentRegistry()
    settings = Settings(
        platform_rag_document_registry_path=str(TEMP_ROOT / "atomic" / "docs.json"),
    )
    user = ScopedUser(
        tenant_id="tenantAtomic",
        user_id="userAtomic",
        scoped_user_id="tenantAtomic:userAtomic",
    )
    request = DocumentCreateRequest(
        name="atomic.pdf",
        content_type="application/pdf",
        size_bytes=1,
    )
    real_replace = document_registry_module.os.replace
    real_fsync = document_registry_module.os.fsync
    replace_calls: list[tuple[Path, Path]] = []
    fsync_calls: list[int] = []

    def capture_replace(src: Any, dst: Any) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        replace_calls.append((src_path, dst_path))
        assert_true(
            src_path.parent == dst_path.parent,
            "Document temp file must be in the target directory.",
        )
        assert_true(
            src_path.name.endswith(".tmp"),
            "Document temp file name should be clearly temporary.",
        )
        real_replace(src, dst)

    def capture_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    document_registry_module.os.replace = capture_replace
    document_registry_module.os.fsync = capture_fsync
    try:
        registry.create(settings, user, "kb_atomic", request)
    finally:
        document_registry_module.os.replace = real_replace
        document_registry_module.os.fsync = real_fsync

    assert_true(len(replace_calls) == 1, "Document registry must call os.replace once.")
    assert_true(len(fsync_calls) >= 1, "Document registry must call os.fsync.")


async def main_async() -> None:
    assert_python_version()
    assert_main_rag_runtime_disabled()
    assert_facade_does_not_call_native_rag()
    app = build_app()
    assert_atomic_replace_behavior()

    headers_a = {"X-Tenant-ID": "tenantA", "X-User-ID": "userA"}
    headers_user_b = {"X-Tenant-ID": "tenantA", "X-User-ID": "userB"}
    headers_tenant_b = {"X-Tenant-ID": "tenantB", "X-User-ID": "userA"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        openapi_paths = (await client.get("/openapi.json")).json()["paths"]
        assert_document_routes(openapi_paths)

        overview = (await client.get("/api/platform/overview")).json()
        assert_true(
            overview["phase"] in {"phase-3.3", "phase-3.4"},
            "Overview phase must be phase-3.3 or later Phase 3.x.",
        )
        features = overview["features"]
        assert_true(features["document_facade_registered"] is True, "Document facade missing.")
        assert_true(
            features["document_registry"] == "local_json_metadata_only",
            "Document registry overview state is wrong.",
        )
        assert_true(features["document_indexing_enabled"] is False, "Indexing must be disabled.")
        assert_true(features["document_runtime_connected"] is False, "Runtime must be disabled.")
        assert_true(features["rag_effective_enabled"] is False, "RAG effective must stay false.")
        assert_true(features["rag_runtime_registered"] is False, "RAG runtime must stay false.")

        kb_create = await client.post(
            "/api/platform/knowledge-bases",
            headers=headers_a,
            json={"name": "Document KB", "description": "metadata only"},
        )
        assert_true(kb_create.status_code == 201, "KB create should return 201.")
        kb_id = kb_create.json()["kb_id"]

        empty_list = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents",
            headers=headers_a,
        )
        assert_true(empty_list.status_code == 200, "Empty document list should return 200.")
        assert_true(empty_list.json()["total"] == 0, "Missing document registry should list empty.")
        assert_true(
            not DOCUMENT_REGISTRY_PATH.exists(),
            "Read-only list must not create document registry file.",
        )
        missing_doc = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents/doc_missing",
            headers=headers_a,
        )
        assert_true(missing_doc.status_code == 404, "Missing document detail should be 404.")
        assert_true(
            not DOCUMENT_REGISTRY_PATH.exists(),
            "Read-only detail must not create document registry file.",
        )

        missing_kb_create = await client.post(
            "/api/platform/knowledge-bases/kb_missing/documents",
            headers=headers_a,
            json={
                "name": "employee-handbook.pdf",
                "source_type": "file",
                "content_type": "application/pdf",
                "size_bytes": 102400,
            },
        )
        assert_true(missing_kb_create.status_code == 404, "Missing parent KB should be 404.")

        for field in (
            "tenant_id",
            "owner_user_id",
            "created_by",
            "status",
            "runtime_enabled",
            "native_document_id",
            "document_id",
            "knowledge_base_id",
            "kb_id",
            "file_path",
            "storage_path",
            "blob_key",
            "checksum",
            "deleted_at",
        ):
            injected = await client.post(
                f"/api/platform/knowledge-bases/{kb_id}/documents",
                headers=headers_a,
                json={
                    "name": "bad.pdf",
                    "source_type": "file",
                    "content_type": "application/pdf",
                    "size_bytes": 1,
                    field: "injected",
                },
            )
            assert_true(injected.status_code == 422, f"Injected field {field} passed.")

        invalid_bodies = (
            {"name": "", "source_type": "file", "content_type": "application/pdf", "size_bytes": 1},
            {"name": "   ", "source_type": "file", "content_type": "application/pdf", "size_bytes": 1},
            {"name": "x" * 256, "source_type": "file", "content_type": "application/pdf", "size_bytes": 1},
            {"name": "ok.pdf", "source_type": "file", "content_type": "", "size_bytes": 1},
            {"name": "ok.pdf", "source_type": "url", "content_type": "application/pdf", "size_bytes": 1},
            {"name": "ok.pdf", "source_type": "file", "content_type": "application/pdf", "size_bytes": -1},
            {"name": "ok.pdf", "source_type": "file", "content_type": "application/pdf", "size_bytes": "not-int"},
        )
        for body in invalid_bodies:
            response = await client.post(
                f"/api/platform/knowledge-bases/{kb_id}/documents",
                headers=headers_a,
                json=body,
            )
            assert_true(response.status_code == 422, f"Invalid body passed: {body!r}")

        document_create = await client.post(
            f"/api/platform/knowledge-bases/{kb_id}/documents",
            headers=headers_a,
            json={
                "name": "employee-handbook.pdf",
                "source_type": "file",
                "content_type": "application/pdf",
                "size_bytes": 102400,
            },
        )
        assert_true(document_create.status_code == 201, "Document create should return 201.")
        doc = document_create.json()
        document_id = doc["document_id"]
        assert_true(document_id.startswith("doc_"), "Document id must be generated.")
        assert_true(doc["knowledge_base_id"] == kb_id, "Document must bind to URL KB.")
        assert_true(doc["tenant_id"] == "tenantA", "Document tenant must come from headers.")
        assert_true(doc["owner_user_id"] == "userA", "Document owner must come from headers.")
        assert_true(doc["created_by"] == "userA", "created_by should be current user.")
        assert_true(doc["status"] == "registered", "Document status must be registered.")
        assert_true(doc["runtime_enabled"] is False, "Document runtime must be disabled.")
        assert_true(doc["native_document_id"] is None, "Native document id must be null.")

        duplicate = await client.post(
            f"/api/platform/knowledge-bases/{kb_id}/documents",
            headers=headers_a,
            json={
                "name": "employee-handbook.pdf",
                "source_type": "file",
                "content_type": "application/pdf",
                "size_bytes": 102400,
            },
        )
        assert_true(duplicate.status_code == 201, "Duplicate document name should be allowed.")
        duplicate_id = duplicate.json()["document_id"]
        assert_true(duplicate_id != document_id, "Duplicate name should create a new id.")

        list_docs = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents",
            headers=headers_a,
        )
        assert_true(list_docs.status_code == 200, "Owner document list should succeed.")
        assert_true(list_docs.json()["total"] == 2, "Owner should see two documents.")

        detail_doc = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents/{document_id}",
            headers=headers_a,
        )
        assert_true(detail_doc.status_code == 200, "Owner document detail should succeed.")

        for headers in (headers_user_b, headers_tenant_b):
            list_other = await client.get(
                f"/api/platform/knowledge-bases/{kb_id}/documents",
                headers=headers,
            )
            assert_true(list_other.status_code == 404, "Cross owner list should be 404.")
            detail_other = await client.get(
                f"/api/platform/knowledge-bases/{kb_id}/documents/{document_id}",
                headers=headers,
            )
            assert_true(detail_other.status_code == 404, "Cross owner detail should be 404.")
            delete_other = await client.delete(
                f"/api/platform/knowledge-bases/{kb_id}/documents/{document_id}",
                headers=headers,
            )
            assert_true(delete_other.status_code == 404, "Cross owner delete should be 404.")

        kb_b = await client.post(
            "/api/platform/knowledge-bases",
            headers=headers_a,
            json={"name": "Wrong KB", "description": ""},
        )
        assert_true(kb_b.status_code == 201, "Second KB create should work.")
        kb_b_id = kb_b.json()["kb_id"]
        wrong_kb_detail = await client.get(
            f"/api/platform/knowledge-bases/{kb_b_id}/documents/{document_id}",
            headers=headers_a,
        )
        assert_true(
            wrong_kb_detail.status_code == 404,
            "Wrong KB + correct document should return 404.",
        )
        wrong_kb_delete = await client.delete(
            f"/api/platform/knowledge-bases/{kb_b_id}/documents/{document_id}",
            headers=headers_a,
        )
        assert_true(
            wrong_kb_delete.status_code == 404,
            "Wrong KB delete should return 404.",
        )

        deleted = await client.delete(
            f"/api/platform/knowledge-bases/{kb_id}/documents/{document_id}",
            headers=headers_a,
        )
        assert_true(deleted.status_code == 200, "Owner document delete should succeed.")
        delete_payload = deleted.json()
        assert_true(delete_payload["deleted"] is True, "Delete response needs deleted=true.")
        assert_true(delete_payload["status"] == "deleted", "Delete status must be deleted.")
        assert_true(delete_payload["knowledge_base_id"] == kb_id, "Delete response needs KB id.")

        list_after_delete = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents",
            headers=headers_a,
        )
        assert_true(
            list_after_delete.json()["total"] == 1,
            "Soft-deleted document should be excluded from list.",
        )
        detail_after_delete = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents/{document_id}",
            headers=headers_a,
        )
        assert_true(detail_after_delete.status_code == 404, "Deleted document detail should be 404.")
        delete_again = await client.delete(
            f"/api/platform/knowledge-bases/{kb_id}/documents/{document_id}",
            headers=headers_a,
        )
        assert_true(delete_again.status_code == 404, "Repeated document delete should be 404.")

        persisted_registry = DocumentRegistry()
        settings = Settings(
            platform_rag_document_registry_path=str(DOCUMENT_REGISTRY_PATH),
        )
        user = ScopedUser(
            tenant_id="tenantA",
            user_id="userA",
            scoped_user_id="tenantA:userA",
        )
        persisted_docs = persisted_registry.list_for_knowledge_base(
            settings,
            user,
            kb_id,
        )
        assert_true(
            len(persisted_docs) == 1 and persisted_docs[0]["document_id"] == duplicate_id,
            "New DocumentRegistry instance should read persisted active document.",
        )
        document_payload = json.loads(DOCUMENT_REGISTRY_PATH.read_text(encoding="utf-8"))
        assert_true(
            document_payload["version"] in {1, 2},
            "Document registry must include a supported version.",
        )
        records = document_payload["documents"]
        deleted_record = next(item for item in records if item["document_id"] == document_id)
        assert_true(deleted_record["status"] == "deleted", "Deleted tombstone must persist.")
        assert_true(deleted_record["deleted_at"], "Deleted document needs deleted_at.")

        delete_kb = await client.delete(
            f"/api/platform/knowledge-bases/{kb_id}",
            headers=headers_a,
        )
        assert_true(delete_kb.status_code == 200, "Parent KB delete should succeed.")
        create_after_kb_delete = await client.post(
            f"/api/platform/knowledge-bases/{kb_id}/documents",
            headers=headers_a,
            json={
                "name": "after-delete.pdf",
                "source_type": "file",
                "content_type": "application/pdf",
                "size_bytes": 1,
            },
        )
        assert_true(create_after_kb_delete.status_code == 404, "Deleted parent KB should block create.")
        list_after_kb_delete = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents",
            headers=headers_a,
        )
        assert_true(list_after_kb_delete.status_code == 404, "Deleted parent KB should block list.")
        get_after_kb_delete = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents/{duplicate_id}",
            headers=headers_a,
        )
        assert_true(get_after_kb_delete.status_code == 404, "Deleted parent KB should block get.")
        delete_after_kb_delete = await client.delete(
            f"/api/platform/knowledge-bases/{kb_id}/documents/{duplicate_id}",
            headers=headers_a,
        )
        assert_true(delete_after_kb_delete.status_code == 404, "Deleted parent KB should block delete.")

        for bad_payload in (
            "{ this is not json",
            json.dumps({"version": 3, "documents": []}),
            json.dumps({"version": 2, "documents": {}}),
            json.dumps({"version": 2, "documents": [{"document_id": "doc_broken"}]}),
        ):
            DOCUMENT_REGISTRY_PATH.write_text(bad_payload, encoding="utf-8")
            corrupt_response = await client.get(
                f"/api/platform/knowledge-bases/{kb_b_id}/documents",
                headers=headers_a,
            )
            assert_true(
                corrupt_response.status_code == 500,
                "Corrupt document registry should return safe 500.",
            )
            corrupt_payload = json.dumps(corrupt_response.json(), ensure_ascii=False)
            assert_true(
                str(DOCUMENT_REGISTRY_PATH) not in corrupt_payload,
                "Document registry errors must not expose paths.",
            )
            assert_true(
                bad_payload not in corrupt_payload,
                "Document registry errors must not expose raw content.",
            )
            assert_true(
                DOCUMENT_REGISTRY_PATH.read_text(encoding="utf-8") == bad_payload,
                "Corrupt document registry must not be overwritten.",
            )

    shutil.rmtree(TEMP_ROOT)
    print("Phase 3.3 Document metadata facade smoke passed.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
