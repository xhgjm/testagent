import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser
from backend.app.rag.config import resolve_rag_config_status
from backend.app.rag.schemas import KnowledgeBaseCreateRequest


REGISTRY_VERSION = 1
REQUIRED_RECORD_FIELDS = {
    "kb_id",
    "tenant_id",
    "owner_user_id",
    "scoped_user_id",
    "name",
    "description",
    "status",
    "runtime_enabled",
    "native_kb_id",
    "native_collection",
    "isolation_strategy",
    "created_at",
    "updated_at",
    "deleted_at",
}
_PROCESS_LOCK = RLock()


class KnowledgeBaseRegistryError(RuntimeError):
    """Raised when the local KnowledgeBase metadata registry is unavailable."""


class KnowledgeBaseRegistry:
    """Small JSON metadata registry for Phase 3.2.

    This registry is deliberately owner-private and local-file based. It does
    not create AgentScope KnowledgeBase objects, vector collections, blob
    storage, parsers, embeddings, or index workers.
    """

    def __init__(self) -> None:
        # Phase 3.2 is a single-process JSON registry. All registry instances
        # share this lock so read-modify-write remains protected in-process.
        self._lock = _PROCESS_LOCK

    def create(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        request: KnowledgeBaseCreateRequest,
    ) -> dict[str, Any]:
        with self._lock:
            records = self._load_records(settings)
            now = _utc_now()
            rag_status = resolve_rag_config_status(settings)
            record = {
                "kb_id": f"kb_{uuid4().hex}",
                "tenant_id": scoped_user.tenant_id,
                "owner_user_id": scoped_user.user_id,
                "scoped_user_id": scoped_user.scoped_user_id,
                "name": request.name,
                "description": request.description,
                "status": "active",
                "runtime_enabled": False,
                "native_kb_id": None,
                "native_collection": None,
                "isolation_strategy": rag_status.isolation_strategy,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
            records.append(record)
            self._save_records(settings, records)
            return record

    def list_for_owner(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
    ) -> list[dict[str, Any]]:
        with self._lock:
            records = self._load_records(settings)
            items = [
                item
                for item in records
                if _is_owner_record(item, scoped_user)
                and item.get("status") == "active"
            ]
            return sorted(
                items,
                key=lambda item: str(item.get("created_at", "")),
                reverse=True,
            )

    def get_for_owner(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        kb_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            for item in self._load_records(settings):
                if (
                    item.get("kb_id") == kb_id
                    and _is_owner_record(item, scoped_user)
                    and item.get("status") == "active"
                ):
                    return item
            return None

    def delete_for_owner(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        kb_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            records = self._load_records(settings)
            now = _utc_now()
            deleted: dict[str, Any] | None = None
            for item in records:
                if (
                    item.get("kb_id") == kb_id
                    and _is_owner_record(item, scoped_user)
                    and item.get("status") == "active"
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

    def _load_records(self, settings: Settings) -> list[dict[str, Any]]:
        path = _registry_path(settings)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KnowledgeBaseRegistryError("KnowledgeBase registry is corrupt.") from exc
        except OSError as exc:
            raise KnowledgeBaseRegistryError("KnowledgeBase registry is unavailable.") from exc

        if not isinstance(payload, dict):
            raise KnowledgeBaseRegistryError("KnowledgeBase registry shape is invalid.")
        if payload.get("version") != REGISTRY_VERSION:
            raise KnowledgeBaseRegistryError("KnowledgeBase registry version is invalid.")

        records = payload.get("knowledge_bases", [])
        if not isinstance(records, list):
            raise KnowledgeBaseRegistryError("KnowledgeBase registry records are invalid.")

        validated_records: list[dict[str, Any]] = []
        for item in records:
            if not _is_valid_record(item):
                raise KnowledgeBaseRegistryError("KnowledgeBase registry record is invalid.")
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
                "version": REGISTRY_VERSION,
                "knowledge_bases": records,
            }
            with tmp_path.open("w", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp_path, path)
        except OSError as exc:
            raise KnowledgeBaseRegistryError("KnowledgeBase registry write failed.") from exc
        finally:
            if "tmp_path" in locals() and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass


def _registry_path(settings: Settings) -> Path:
    path = Path(settings.platform_rag_kb_registry_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _is_owner_record(item: dict[str, Any], scoped_user: ScopedUser) -> bool:
    return (
        item.get("tenant_id") == scoped_user.tenant_id
        and item.get("owner_user_id") == scoped_user.user_id
    )


def _is_valid_record(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if not REQUIRED_RECORD_FIELDS.issubset(item.keys()):
        return False
    if not isinstance(item.get("kb_id"), str) or not item["kb_id"].startswith("kb_"):
        return False
    if item.get("status") not in {"active", "deleted"}:
        return False
    if item.get("runtime_enabled") is not False:
        return False
    if item.get("native_kb_id") is not None:
        return False
    if item.get("native_collection") is not None:
        return False
    for field in (
        "tenant_id",
        "owner_user_id",
        "scoped_user_id",
        "name",
        "description",
        "isolation_strategy",
        "created_at",
        "updated_at",
    ):
        if not isinstance(item.get(field), str):
            return False
    if item.get("deleted_at") is not None and not isinstance(item.get("deleted_at"), str):
        return False
    return True
