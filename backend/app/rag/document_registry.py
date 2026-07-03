import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser
from backend.app.rag.schemas import DocumentCreateRequest


DOCUMENT_REGISTRY_VERSION = 2
REQUIRED_DOCUMENT_FIELDS = {
    "document_id",
    "knowledge_base_id",
    "tenant_id",
    "owner_user_id",
    "created_by",
    "name",
    "source_type",
    "content_type",
    "size_bytes",
    "status",
    "runtime_enabled",
    "native_document_id",
    "storage_key",
    "checksum_sha256",
    "parser_name",
    "chunker_name",
    "chunk_count",
    "uploaded_at",
    "parsed_at",
    "error_code",
    "created_at",
    "updated_at",
    "deleted_at",
}
_PROCESS_LOCK = RLock()


class DocumentRegistryError(RuntimeError):
    """Raised when the local Document metadata registry is unavailable."""


class DocumentRegistry:
    """Small JSON metadata registry for Phase 3.3 documents.

    The registry stores metadata only. It never stores file bytes, parsed text,
    chunks, embeddings, vector ids, blob keys, or filesystem paths.
    """

    def __init__(self) -> None:
        # Phase 3.3 is single-process JSON metadata storage. All registry
        # instances share this lock so read-modify-write is protected in-process.
        self._lock = _PROCESS_LOCK

    def create(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        request: DocumentCreateRequest,
    ) -> dict[str, Any]:
        with self._lock:
            records = self._load_records(settings)
            now = _utc_now()
            record = {
                "document_id": f"doc_{uuid4().hex}",
                "knowledge_base_id": knowledge_base_id,
                "tenant_id": scoped_user.tenant_id,
                "owner_user_id": scoped_user.user_id,
                "created_by": scoped_user.user_id,
                "name": request.name,
                "source_type": request.source_type,
                "content_type": request.content_type,
                "size_bytes": request.size_bytes,
                "status": "registered",
                "runtime_enabled": False,
                "native_document_id": None,
                "storage_key": None,
                "checksum_sha256": None,
                "parser_name": None,
                "chunker_name": None,
                "chunk_count": 0,
                "uploaded_at": None,
                "parsed_at": None,
                "error_code": None,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
            records.append(record)
            self._save_records(settings, records)
            return record

    def list_for_knowledge_base(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
    ) -> list[dict[str, Any]]:
        with self._lock:
            records = self._load_records(settings)
            items = [
                item
                for item in records
                if _is_owner_document(item, scoped_user, knowledge_base_id)
                and item.get("status") != "deleted"
            ]
            return sorted(
                items,
                key=lambda item: str(item.get("created_at", "")),
                reverse=True,
            )

    def get_for_knowledge_base(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        document_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            for item in self._load_records(settings):
                if (
                    item.get("document_id") == document_id
                    and _is_owner_document(item, scoped_user, knowledge_base_id)
                    and item.get("status") != "deleted"
                ):
                    return item
            return None

    def delete_for_knowledge_base(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        document_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            records = self._load_records(settings)
            now = _utc_now()
            deleted: dict[str, Any] | None = None
            for item in records:
                if (
                    item.get("document_id") == document_id
                    and _is_owner_document(item, scoped_user, knowledge_base_id)
                    and item.get("status") != "deleted"
                ):
                    item["status"] = "deleted"
                    item["updated_at"] = now
                    item["deleted_at"] = now
                    deleted = item
                    break
            if deleted is None:
                return None
            self._save_records(settings, records)
            return deleted

    def update_for_processing(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        document_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._lock:
            records = self._load_records(settings)
            updated: dict[str, Any] | None = None
            allowed_fields = {
                "status",
                "storage_key",
                "checksum_sha256",
                "parser_name",
                "chunker_name",
                "chunk_count",
                "uploaded_at",
                "parsed_at",
                "error_code",
            }
            for item in records:
                if (
                    item.get("document_id") == document_id
                    and _is_owner_document(item, scoped_user, knowledge_base_id)
                    and item.get("status") != "deleted"
                ):
                    for key, value in updates.items():
                        if key in allowed_fields:
                            item[key] = value
                    item["updated_at"] = _utc_now()
                    updated = item
                    break
            if updated is None:
                return None
            self._save_records(settings, records)
            return updated

    def _load_records(self, settings: Settings) -> list[dict[str, Any]]:
        path = _registry_path(settings)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DocumentRegistryError("Document registry is corrupt.") from exc
        except OSError as exc:
            raise DocumentRegistryError("Document registry is unavailable.") from exc

        if not isinstance(payload, dict):
            raise DocumentRegistryError("Document registry shape is invalid.")
        version = payload.get("version")
        if version not in {1, DOCUMENT_REGISTRY_VERSION}:
            raise DocumentRegistryError("Document registry version is invalid.")

        records = payload.get("documents", [])
        if not isinstance(records, list):
            raise DocumentRegistryError("Document registry records are invalid.")

        validated_records: list[dict[str, Any]] = []
        for item in records:
            if version == 1:
                item = _upgrade_v1_record(item)
            if not _is_valid_record(item):
                raise DocumentRegistryError("Document registry record is invalid.")
            validated_records.append(item)
        return validated_records

    def _save_records(
        self,
        settings: Settings,
        records: list[dict[str, Any]],
    ) -> None:
        path = _registry_path(settings)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
            payload = {
                "version": DOCUMENT_REGISTRY_VERSION,
                "documents": records,
            }
            with tmp_path.open("w", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp_path, path)
        except OSError as exc:
            raise DocumentRegistryError("Document registry write failed.") from exc
        finally:
            if "tmp_path" in locals() and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass


def _registry_path(settings: Settings) -> Path:
    path = Path(settings.platform_rag_document_registry_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _is_owner_document(
    item: dict[str, Any],
    scoped_user: ScopedUser,
    knowledge_base_id: str,
) -> bool:
    return (
        item.get("knowledge_base_id") == knowledge_base_id
        and item.get("tenant_id") == scoped_user.tenant_id
        and item.get("owner_user_id") == scoped_user.user_id
    )


def _is_valid_record(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if not REQUIRED_DOCUMENT_FIELDS.issubset(item.keys()):
        return False
    if (
        not isinstance(item.get("document_id"), str)
        or not item["document_id"].startswith("doc_")
    ):
        return False
    if not isinstance(item.get("knowledge_base_id"), str):
        return False
    if item.get("status") not in {
        "registered",
        "uploaded",
        "parsing",
        "parsed",
        "failed",
        "deleted",
    }:
        return False
    if item.get("source_type") != "file":
        return False
    if not isinstance(item.get("size_bytes"), int) or item["size_bytes"] < 0:
        return False
    if item.get("runtime_enabled") is not False:
        return False
    if item.get("native_document_id") is not None:
        return False
    if item.get("storage_key") is not None and not isinstance(item.get("storage_key"), str):
        return False
    for nullable_string in (
        "checksum_sha256",
        "parser_name",
        "chunker_name",
        "uploaded_at",
        "parsed_at",
        "error_code",
    ):
        if item.get(nullable_string) is not None and not isinstance(
            item.get(nullable_string),
            str,
        ):
            return False
    if not isinstance(item.get("chunk_count"), int) or item["chunk_count"] < 0:
        return False
    for field in (
        "tenant_id",
        "owner_user_id",
        "created_by",
        "name",
        "content_type",
        "created_at",
        "updated_at",
    ):
        if not isinstance(item.get(field), str):
            return False
    if item.get("deleted_at") is not None and not isinstance(item.get("deleted_at"), str):
        return False
    return True


def _upgrade_v1_record(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return item
    upgraded = dict(item)
    upgraded.setdefault("storage_key", None)
    upgraded.setdefault("checksum_sha256", None)
    upgraded.setdefault("parser_name", None)
    upgraded.setdefault("chunker_name", None)
    upgraded.setdefault("chunk_count", 0)
    upgraded.setdefault("uploaded_at", None)
    upgraded.setdefault("parsed_at", None)
    upgraded.setdefault("error_code", None)
    return upgraded
