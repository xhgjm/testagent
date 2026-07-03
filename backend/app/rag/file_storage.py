import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser


SUPPORTED_CONTENT_TYPES = {
    "text/plain": {".txt"},
    "text/markdown": {".md", ".markdown"},
    "text/x-markdown": {".md", ".markdown"},
    "application/pdf": {".pdf"},
}
CONTENT_TYPE_ALIASES = {
    "text/plain": {"text/plain"},
    "text/markdown": {"text/markdown", "text/x-markdown"},
    "text/x-markdown": {"text/markdown", "text/x-markdown"},
    "application/pdf": {"application/pdf"},
}


class FileStorageError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class StoredFile:
    storage_key: str
    path: Path
    size_bytes: int
    checksum_sha256: str


def validate_upload_config(settings: Settings) -> None:
    if settings.platform_rag_max_upload_bytes <= 0:
        raise FileStorageError("INVALID_RAG_UPLOAD_CONFIG")
    if settings.platform_rag_chunk_size <= 0:
        raise FileStorageError("INVALID_RAG_CHUNK_CONFIG")
    if not 0 <= settings.platform_rag_chunk_overlap < settings.platform_rag_chunk_size:
        raise FileStorageError("INVALID_RAG_CHUNK_CONFIG")


def validate_declared_content_type(content_type: str) -> None:
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise FileStorageError("UNSUPPORTED_DOCUMENT_TYPE")


def validate_upload_content_type(
    declared_content_type: str,
    upload_content_type: str | None,
) -> None:
    validate_declared_content_type(declared_content_type)
    if (upload_content_type or "").lower() not in CONTENT_TYPE_ALIASES[declared_content_type]:
        raise FileStorageError("UNSUPPORTED_DOCUMENT_TYPE")


async def save_upload_file(
    settings: Settings,
    scoped_user: ScopedUser,
    knowledge_base_id: str,
    document_id: str,
    declared_content_type: str,
    expected_size_bytes: int,
    upload: UploadFile,
) -> StoredFile:
    validate_upload_config(settings)
    validate_upload_content_type(declared_content_type, upload.content_type)

    extension = _safe_extension(upload.filename or "", declared_content_type)
    root = _storage_root(settings)
    final_dir = _document_dir(root, scoped_user, knowledge_base_id, document_id)
    final_path = final_dir / f"source{extension}"
    _ensure_within_root(root, final_path)

    final_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = final_dir / f"source.{uuid4().hex}.tmp"
    hasher = hashlib.sha256()
    total = 0

    try:
        with tmp_path.open("wb") as file:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.platform_rag_max_upload_bytes:
                    raise FileStorageError("DOCUMENT_TOO_LARGE")
                hasher.update(chunk)
                file.write(chunk)
            file.flush()
            os.fsync(file.fileno())

        if total != expected_size_bytes:
            raise FileStorageError("DOCUMENT_SIZE_MISMATCH")

        os.replace(tmp_path, final_path)
        storage_key = _storage_key(scoped_user, knowledge_base_id, document_id, extension)
        return StoredFile(
            storage_key=storage_key,
            path=final_path,
            size_bytes=total,
            checksum_sha256=hasher.hexdigest(),
        )
    except FileStorageError:
        _safe_unlink(tmp_path)
        raise
    except OSError as exc:
        _safe_unlink(tmp_path)
        raise FileStorageError("DOCUMENT_STORAGE_FAILED") from exc
    finally:
        await upload.close()


def _storage_root(settings: Settings) -> Path:
    root = Path(settings.platform_rag_file_storage_root)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _safe_extension(filename: str, declared_content_type: str) -> str:
    suffix = Path(filename).suffix.lower()
    allowed = SUPPORTED_CONTENT_TYPES[declared_content_type]
    if suffix not in allowed:
        if declared_content_type == "text/plain":
            suffix = ".txt"
        elif declared_content_type in {"text/markdown", "text/x-markdown"}:
            suffix = ".md"
        elif declared_content_type == "application/pdf":
            suffix = ".pdf"
    if suffix not in allowed:
        raise FileStorageError("UNSUPPORTED_DOCUMENT_TYPE")
    return suffix


def _document_dir(
    root: Path,
    scoped_user: ScopedUser,
    knowledge_base_id: str,
    document_id: str,
) -> Path:
    tenant_scope = hashlib.sha256(scoped_user.tenant_id.encode("utf-8")).hexdigest()[:24]
    user_scope = hashlib.sha256(scoped_user.user_id.encode("utf-8")).hexdigest()[:24]
    return (root / tenant_scope / user_scope / knowledge_base_id / document_id).resolve()


def _storage_key(
    scoped_user: ScopedUser,
    knowledge_base_id: str,
    document_id: str,
    extension: str,
) -> str:
    tenant_scope = hashlib.sha256(scoped_user.tenant_id.encode("utf-8")).hexdigest()[:24]
    user_scope = hashlib.sha256(scoped_user.user_id.encode("utf-8")).hexdigest()[:24]
    return f"{tenant_scope}/{user_scope}/{knowledge_base_id}/{document_id}/source{extension}"


def _ensure_within_root(root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise FileStorageError("DOCUMENT_STORAGE_FAILED") from exc


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
