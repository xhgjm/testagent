import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser
from backend.app.rag.chunking import TextChunk


CHUNK_REGISTRY_VERSION = 1
REQUIRED_CHUNK_FIELDS = {
    "chunk_id",
    "document_id",
    "knowledge_base_id",
    "tenant_id",
    "owner_user_id",
    "sequence",
    "text",
    "char_count",
    "checksum_sha256",
    "status",
    "created_at",
}
_PROCESS_LOCK = RLock()


class ChunkRegistryError(RuntimeError):
    """Raised when the local Chunk registry is unavailable."""


class ChunkRegistry:
    def __init__(self) -> None:
        self._lock = _PROCESS_LOCK

    def replace_document_chunks(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        document_id: str,
        chunks: list[TextChunk],
    ) -> list[dict[str, Any]]:
        with self._lock:
            records = self._load_records(settings)
            now = _utc_now()
            for item in records:
                if _is_document_chunk(item, scoped_user, knowledge_base_id, document_id):
                    item["status"] = "deleted"
            new_records = [
                {
                    "chunk_id": f"chunk_{uuid4().hex}",
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "tenant_id": scoped_user.tenant_id,
                    "owner_user_id": scoped_user.user_id,
                    "sequence": chunk.sequence,
                    "text": chunk.text,
                    "char_count": chunk.char_count,
                    "checksum_sha256": chunk.checksum_sha256,
                    "status": "active",
                    "created_at": now,
                }
                for chunk in chunks
            ]
            records.extend(new_records)
            self._save_records(settings, records)
            return new_records

    def list_document_chunks(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        document_id: str,
    ) -> list[dict[str, Any]]:
        with self._lock:
            chunks = [
                item
                for item in self._load_records(settings)
                if _is_document_chunk(item, scoped_user, knowledge_base_id, document_id)
                and item.get("status") == "active"
            ]
            return sorted(chunks, key=lambda item: int(item.get("sequence", 0)))

    def mark_document_chunks_deleted(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        document_id: str,
    ) -> None:
        with self._lock:
            records = self._load_records(settings)
            changed = False
            for item in records:
                if (
                    _is_document_chunk(item, scoped_user, knowledge_base_id, document_id)
                    and item.get("status") == "active"
                ):
                    item["status"] = "deleted"
                    changed = True
            if changed:
                self._save_records(settings, records)

    def _load_records(self, settings: Settings) -> list[dict[str, Any]]:
        path = _registry_path(settings)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ChunkRegistryError("Chunk registry is corrupt.") from exc
        except OSError as exc:
            raise ChunkRegistryError("Chunk registry is unavailable.") from exc

        if not isinstance(payload, dict) or payload.get("version") != CHUNK_REGISTRY_VERSION:
            raise ChunkRegistryError("Chunk registry version is invalid.")
        records = payload.get("chunks", [])
        if not isinstance(records, list):
            raise ChunkRegistryError("Chunk registry records are invalid.")
        for item in records:
            if not _is_valid_record(item):
                raise ChunkRegistryError("Chunk registry record is invalid.")
        return records

    def _save_records(self, settings: Settings, records: list[dict[str, Any]]) -> None:
        path = _registry_path(settings)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
            payload = {"version": CHUNK_REGISTRY_VERSION, "chunks": records}
            with tmp_path.open("w", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp_path, path)
        except OSError as exc:
            raise ChunkRegistryError("Chunk registry write failed.") from exc
        finally:
            if "tmp_path" in locals() and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass


def _registry_path(settings: Settings) -> Path:
    path = Path(settings.platform_rag_chunk_registry_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _is_document_chunk(
    item: dict[str, Any],
    scoped_user: ScopedUser,
    knowledge_base_id: str,
    document_id: str,
) -> bool:
    return (
        item.get("document_id") == document_id
        and item.get("knowledge_base_id") == knowledge_base_id
        and item.get("tenant_id") == scoped_user.tenant_id
        and item.get("owner_user_id") == scoped_user.user_id
    )


def _is_valid_record(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if not REQUIRED_CHUNK_FIELDS.issubset(item.keys()):
        return False
    if not isinstance(item.get("chunk_id"), str) or not item["chunk_id"].startswith("chunk_"):
        return False
    if item.get("status") not in {"active", "deleted"}:
        return False
    if not isinstance(item.get("sequence"), int) or item["sequence"] < 0:
        return False
    if not isinstance(item.get("text"), str) or not item["text"].strip():
        return False
    if not isinstance(item.get("char_count"), int) or item["char_count"] != len(item["text"]):
        return False
    for field in (
        "document_id",
        "knowledge_base_id",
        "tenant_id",
        "owner_user_id",
        "checksum_sha256",
        "created_at",
    ):
        if not isinstance(item.get(field), str):
            return False
    return True
