import asyncio
import hashlib
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import Settings, get_settings
from backend.app.platform.routes import router as platform_router
from backend.app.platform.security import ScopedUser
from backend.app.rag.chunk_registry import ChunkRegistry
from backend.app.rag.document_registry import DocumentRegistry
from backend.app.rag.routes import router as rag_router


TEMP_ROOT = PROJECT_ROOT / ".cache" / "p34_smoke"
KB_REGISTRY_PATH = TEMP_ROOT / "knowledge-bases.json"
DOCUMENT_REGISTRY_PATH = TEMP_ROOT / "documents.json"
CHUNK_REGISTRY_PATH = TEMP_ROOT / "chunks.json"
FILE_STORAGE_ROOT = TEMP_ROOT / "files"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_app(*, max_upload_bytes: int = 4096) -> FastAPI:
    settings = Settings(
        platform_rag_kb_registry_path=str(KB_REGISTRY_PATH),
        platform_rag_document_registry_path=str(DOCUMENT_REGISTRY_PATH),
        platform_rag_chunk_registry_path=str(CHUNK_REGISTRY_PATH),
        platform_rag_file_storage_root=str(FILE_STORAGE_ROOT),
        platform_rag_max_upload_bytes=max_upload_bytes,
        platform_rag_chunk_size=80,
        platform_rag_chunk_overlap=10,
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
    assert_true(sys.version_info >= (3, 11), f"Python 3.11+ required, got {sys.version}.")


def assert_main_rag_runtime_disabled() -> None:
    source = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    for needle in (
        "knowledge_base_manager=None",
        "knowledge_parsers=None",
        "knowledge_chunker=None",
        "blob_store=None",
        "enable_index_worker=False",
    ):
        assert_true(needle in source, f"main.py must keep {needle}.")


def assert_no_native_rag_calls() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            PROJECT_ROOT / "backend" / "app" / "rag" / "routes.py",
            PROJECT_ROOT / "backend" / "app" / "rag" / "document_processing.py",
            PROJECT_ROOT / "backend" / "app" / "rag" / "file_storage.py",
            PROJECT_ROOT / "backend" / "app" / "rag" / "parsing.py",
        )
    )
    for forbidden in ("AgentScopeNativeClient", "/knowledge_bases", "QdrantStore", "Embedding"):
        assert_true(forbidden not in sources, f"Unexpected native RAG dependency: {forbidden}.")


async def create_kb(client: httpx.AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post(
        "/api/platform/knowledge-bases",
        headers=headers,
        json={"name": name, "description": "phase 3.4 smoke"},
    )
    assert_true(response.status_code == 201, response.text)
    return response.json()["kb_id"]


async def create_doc(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    *,
    name: str,
    content_type: str,
    size_bytes: int,
) -> str:
    response = await client.post(
        f"/api/platform/knowledge-bases/{kb_id}/documents",
        headers=headers,
        json={
            "name": name,
            "source_type": "file",
            "content_type": content_type,
            "size_bytes": size_bytes,
        },
    )
    assert_true(response.status_code == 201, response.text)
    return response.json()["document_id"]


async def upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_id: str,
    document_id: str,
    *,
    filename: str,
    content_type: str,
    data: bytes,
) -> httpx.Response:
    return await client.post(
        f"/api/platform/knowledge-bases/{kb_id}/documents/{document_id}/upload",
        headers=headers,
        files={"file": (filename, data, content_type)},
    )


async def main_async() -> None:
    global TEMP_ROOT, KB_REGISTRY_PATH, DOCUMENT_REGISTRY_PATH, CHUNK_REGISTRY_PATH, FILE_STORAGE_ROOT

    assert_python_version()
    assert_main_rag_runtime_disabled()
    assert_no_native_rag_calls()

    TEMP_ROOT = PROJECT_ROOT / ".cache" / f"p34_{uuid.uuid4().hex[:12]}"
    KB_REGISTRY_PATH = TEMP_ROOT / "knowledge-bases.json"
    DOCUMENT_REGISTRY_PATH = TEMP_ROOT / "documents.json"
    CHUNK_REGISTRY_PATH = TEMP_ROOT / "chunks.json"
    FILE_STORAGE_ROOT = TEMP_ROOT / "files"

    headers_a = {"X-Tenant-ID": "tenantA", "X-User-ID": "userA"}
    headers_user_b = {"X-Tenant-ID": "tenantA", "X-User-ID": "userB"}
    headers_tenant_b = {"X-Tenant-ID": "tenantB", "X-User-ID": "userA"}

    app = build_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        openapi_paths = (await client.get("/openapi.json")).json()["paths"]
        upload_path = "/api/platform/knowledge-bases/{kb_id}/documents/{document_id}/upload"
        assert_true(
            list(openapi_paths[upload_path].keys()) == ["post"],
            "Upload route must expose only POST.",
        )
        assert_true(
            not any("search" in path or "chunks" in path for path in openapi_paths),
            "Phase 3.4 must not expose public search/chunk APIs.",
        )

        overview = (await client.get("/api/platform/overview")).json()
        features = overview["features"]
        assert_true(overview["phase"] == "phase-3.4", "Overview phase must be phase-3.4.")
        assert_true(features["document_binary_upload_enabled"] is True, "Upload should be enabled.")
        assert_true(features["document_parsing_enabled"] is True, "Parsing should be enabled.")
        assert_true(features["document_chunking_enabled"] is True, "Chunking should be enabled.")
        assert_true(features["document_indexing_enabled"] is False, "Indexing must stay disabled.")
        assert_true(features["document_embedding_enabled"] is False, "Embedding must stay disabled.")
        assert_true(features["document_search_enabled"] is False, "Search must stay disabled.")
        assert_true(features["rag_effective_enabled"] is False, "RAG runtime must stay disabled.")
        assert_true(features["rag_runtime_registered"] is False, "RAG runtime must stay unregistered.")

        kb_id = await create_kb(client, headers_a, "Processing KB")

        # Phase 3.3 v1 compatibility: create v1 document registry and ensure read does not rewrite.
        v1_doc_id = "doc_v1compat"
        v1_payload = {
            "version": 1,
            "documents": [
                {
                    "document_id": v1_doc_id,
                    "knowledge_base_id": kb_id,
                    "tenant_id": "tenantA",
                    "owner_user_id": "userA",
                    "created_by": "userA",
                    "name": "legacy.txt",
                    "source_type": "file",
                    "content_type": "text/plain",
                    "size_bytes": 5,
                    "status": "registered",
                    "runtime_enabled": False,
                    "native_document_id": None,
                    "created_at": "2026-07-03T00:00:00+00:00",
                    "updated_at": "2026-07-03T00:00:00+00:00",
                    "deleted_at": None,
                },
            ],
        }
        DOCUMENT_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOCUMENT_REGISTRY_PATH.write_text(json.dumps(v1_payload), encoding="utf-8")
        before_v1 = DOCUMENT_REGISTRY_PATH.read_text(encoding="utf-8")
        legacy_list = await client.get(
            f"/api/platform/knowledge-bases/{kb_id}/documents",
            headers=headers_a,
        )
        assert_true(legacy_list.status_code == 200, legacy_list.text)
        assert_true(legacy_list.json()["total"] == 1, "v1 document should be readable.")
        assert_true(
            DOCUMENT_REGISTRY_PATH.read_text(encoding="utf-8") == before_v1,
            "Read-only v1 access must not rewrite registry.",
        )
        txt_data = b"Hello world. This is a deterministic upload smoke test.\n" * 8
        txt_doc = await create_doc(
            client,
            headers_a,
            kb_id,
            name="hello.txt",
            content_type="text/plain",
            size_bytes=len(txt_data),
        )
        upgraded = json.loads(DOCUMENT_REGISTRY_PATH.read_text(encoding="utf-8"))
        assert_true(upgraded["version"] == 2, "Mutation should upgrade document registry to v2.")
        assert_true(
            any(item["document_id"] == v1_doc_id for item in upgraded["documents"]),
            "v1 record must not be lost during upgrade.",
        )

        txt_response = await upload(
            client,
            headers_a,
            kb_id,
            txt_doc,
            filename="../../escape.txt",
            content_type="text/plain",
            data=txt_data,
        )
        assert_true(txt_response.status_code == 200, txt_response.text)
        txt_payload = txt_response.json()
        assert_true(txt_payload["status"] == "parsed", "TXT document should be parsed.")
        assert_true(
            txt_payload["checksum_sha256"] == hashlib.sha256(txt_data).hexdigest(),
            "Checksum must match uploaded bytes.",
        )
        assert_true(txt_payload["parser_name"] == "plain_text_utf8", "TXT parser name mismatch.")
        assert_true(txt_payload["chunker_name"] == "local_character_v1", "Chunker name mismatch.")
        assert_true(txt_payload["chunk_count"] > 0, "TXT upload should create chunks.")
        assert_true("storage_key" not in txt_payload, "API response must not expose storage key.")

        chunk_payload = json.loads(CHUNK_REGISTRY_PATH.read_text(encoding="utf-8"))
        active_chunks = [
            item
            for item in chunk_payload["chunks"]
            if item["document_id"] == txt_doc and item["status"] == "active"
        ]
        assert_true(len(active_chunks) == txt_payload["chunk_count"], "Chunk count mismatch.")
        sequences = [item["sequence"] for item in active_chunks]
        assert_true(sequences == list(range(len(sequences))), "Chunk sequences must be stable.")
        for chunk in active_chunks:
            assert_true(chunk["tenant_id"] == "tenantA", "Chunk tenant missing.")
            assert_true(chunk["owner_user_id"] == "userA", "Chunk owner missing.")
            assert_true(chunk["knowledge_base_id"] == kb_id, "Chunk KB missing.")
            assert_true(chunk["text"].strip(), "Chunk text must not be empty.")
            assert_true(chunk["char_count"] == len(chunk["text"]), "Chunk char_count mismatch.")
            assert_true(
                chunk["checksum_sha256"]
                == hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest(),
                "Chunk checksum mismatch.",
            )

        parsed_again = await upload(
            client,
            headers_a,
            kb_id,
            txt_doc,
            filename="again.txt",
            content_type="text/plain",
            data=txt_data,
        )
        assert_true(parsed_again.status_code == 409, "Parsed document re-upload must be 409.")

        md_data = b"# Title\n\nThis markdown body should survive parsing.\n"
        md_doc = await create_doc(
            client,
            headers_a,
            kb_id,
            name="notes.md",
            content_type="text/markdown",
            size_bytes=len(md_data),
        )
        md_response = await upload(
            client,
            headers_a,
            kb_id,
            md_doc,
            filename="notes.md",
            content_type="text/markdown",
            data=md_data,
        )
        assert_true(md_response.status_code == 200, md_response.text)
        assert_true(md_response.json()["parser_name"] == "markdown_text_utf8", "Markdown parser mismatch.")
        md_chunks = ChunkRegistry().list_document_chunks(
            Settings(
                platform_rag_chunk_registry_path=str(CHUNK_REGISTRY_PATH),
            ),
            ScopedUser(tenant_id="tenantA", user_id="userA", scoped_user_id="tenantA:userA"),
            kb_id,
            md_doc,
        )
        assert_true(any("Title" in item["text"] for item in md_chunks), "Markdown title lost.")

        if importlib.util.find_spec("pypdf") is None:
            print("PDF parser smoke skipped: pypdf is not installed in this local env.")
        else:
            # Kept intentionally small; pypdf availability is checked above.
            pdf_data = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
            pdf_doc = await create_doc(
                client,
                headers_a,
                kb_id,
                name="empty.pdf",
                content_type="application/pdf",
                size_bytes=len(pdf_data),
            )
            pdf_response = await upload(
                client,
                headers_a,
                kb_id,
                pdf_doc,
                filename="empty.pdf",
                content_type="application/pdf",
                data=pdf_data,
            )
            assert_true(pdf_response.status_code in {422, 500}, "Minimal invalid PDF should fail safely.")

        unsupported_doc = await create_doc(
            client,
            headers_a,
            kb_id,
            name="image.png",
            content_type="image/png",
            size_bytes=4,
        )
        unsupported = await upload(
            client,
            headers_a,
            kb_id,
            unsupported_doc,
            filename="image.png",
            content_type="image/png",
            data=b"data",
        )
        assert_true(unsupported.status_code == 415, "Unsupported type should return 415.")

        big_doc = await create_doc(
            client,
            headers_a,
            kb_id,
            name="big.txt",
            content_type="text/plain",
            size_bytes=5000,
        )
        too_large = await upload(
            client,
            headers_a,
            kb_id,
            big_doc,
            filename="big.txt",
            content_type="text/plain",
            data=b"x" * 5000,
        )
        assert_true(too_large.status_code == 413, "Oversized upload should return 413.")

        mismatch_doc = await create_doc(
            client,
            headers_a,
            kb_id,
            name="mismatch.txt",
            content_type="text/plain",
            size_bytes=100,
        )
        mismatch = await upload(
            client,
            headers_a,
            kb_id,
            mismatch_doc,
            filename="mismatch.txt",
            content_type="text/plain",
            data=b"short",
        )
        assert_true(mismatch.status_code == 409, "Size mismatch should return 409.")

        invalid_doc = await create_doc(
            client,
            headers_a,
            kb_id,
            name="bad-encoding.txt",
            content_type="text/plain",
            size_bytes=2,
        )
        invalid_text = await upload(
            client,
            headers_a,
            kb_id,
            invalid_doc,
            filename="bad.txt",
            content_type="text/plain",
            data=b"\xff\xfe",
        )
        assert_true(invalid_text.status_code == 422, "Invalid UTF-8 should return 422.")

        for headers in (headers_tenant_b, headers_user_b):
            denied = await upload(
                client,
                headers,
                kb_id,
                md_doc,
                filename="deny.md",
                content_type="text/markdown",
                data=md_data,
            )
            assert_true(denied.status_code == 404, "Cross tenant/user upload should return 404.")

        kb_b = await create_kb(client, headers_a, "Wrong KB")
        wrong_kb = await upload(
            client,
            headers_a,
            kb_b,
            md_doc,
            filename="wrong.md",
            content_type="text/markdown",
            data=md_data,
        )
        assert_true(wrong_kb.status_code == 404, "Wrong KB + document should return 404.")

        delete_doc = await client.delete(
            f"/api/platform/knowledge-bases/{kb_id}/documents/{md_doc}",
            headers=headers_a,
        )
        assert_true(delete_doc.status_code == 200, "Document delete should work.")
        deleted_chunks = ChunkRegistry().list_document_chunks(
            Settings(platform_rag_chunk_registry_path=str(CHUNK_REGISTRY_PATH)),
            ScopedUser(tenant_id="tenantA", user_id="userA", scoped_user_id="tenantA:userA"),
            kb_id,
            md_doc,
        )
        assert_true(deleted_chunks == [], "Deleted document chunks should not remain active.")
        deleted_upload = await upload(
            client,
            headers_a,
            kb_id,
            md_doc,
            filename="deleted.md",
            content_type="text/markdown",
            data=md_data,
        )
        assert_true(deleted_upload.status_code == 404, "Deleted document upload should return 404.")

        delete_kb = await client.delete(f"/api/platform/knowledge-bases/{kb_id}", headers=headers_a)
        assert_true(delete_kb.status_code == 200, "Parent KB delete should work.")
        after_kb_delete = await upload(
            client,
            headers_a,
            kb_id,
            unsupported_doc,
            filename="after.txt",
            content_type="text/plain",
            data=b"data",
        )
        assert_true(after_kb_delete.status_code == 404, "Deleted parent KB should block upload.")

        # Corrupt chunk registry should fail safely and not mark a document parsed.
        kb_c = await create_kb(client, headers_a, "Corrupt Chunk KB")
        corrupt_data = b"corrupt chunk registry test"
        corrupt_doc = await create_doc(
            client,
            headers_a,
            kb_c,
            name="corrupt.txt",
            content_type="text/plain",
            size_bytes=len(corrupt_data),
        )
        bad_payload = "{ this is not json"
        CHUNK_REGISTRY_PATH.write_text(bad_payload, encoding="utf-8")
        corrupt = await upload(
            client,
            headers_a,
            kb_c,
            corrupt_doc,
            filename="corrupt.txt",
            content_type="text/plain",
            data=corrupt_data,
        )
        assert_true(corrupt.status_code == 500, "Corrupt chunk registry should return 500.")
        assert_true(
            CHUNK_REGISTRY_PATH.read_text(encoding="utf-8") == bad_payload,
            "Corrupt chunk registry must not be overwritten.",
        )
        corrupt_detail = await client.get(
            f"/api/platform/knowledge-bases/{kb_c}/documents/{corrupt_doc}",
            headers=headers_a,
        )
        assert_true(corrupt_detail.json()["status"] == "failed", "Corrupt chunks should mark failed.")

        # Cross-instance persistence.
        persisted_docs = DocumentRegistry().list_for_knowledge_base(
            Settings(platform_rag_document_registry_path=str(DOCUMENT_REGISTRY_PATH)),
            ScopedUser(tenant_id="tenantA", user_id="userA", scoped_user_id="tenantA:userA"),
            kb_b,
        )
        assert_true(isinstance(persisted_docs, list), "Document registry should be readable cross-instance.")
        assert_true(any(FILE_STORAGE_ROOT.rglob("source.txt")), "Stored TXT source file should persist.")

    shutil.rmtree(TEMP_ROOT)
    shutil.rmtree(TEMP_ROOT, ignore_errors=True)
    print("Phase 3.4 Document upload, parsing and chunking smoke passed.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
