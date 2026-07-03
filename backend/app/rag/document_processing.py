from dataclasses import dataclass

from fastapi import UploadFile

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser
from backend.app.rag.chunk_registry import ChunkRegistry, ChunkRegistryError
from backend.app.rag.chunking import ChunkingError, chunk_text
from backend.app.rag.document_registry import DocumentRegistry, DocumentRegistryError
from backend.app.rag.file_storage import FileStorageError, save_upload_file, validate_upload_config
from backend.app.rag.parsing import DocumentParseError, parse_document


class DocumentProcessingError(RuntimeError):
    def __init__(self, error_code: str, status_code: int) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code


@dataclass(frozen=True)
class DocumentProcessingService:
    document_registry: DocumentRegistry
    chunk_registry: ChunkRegistry

    async def upload_parse_and_chunk(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        document: dict,
        upload: UploadFile,
    ) -> dict:
        document_id = document["document_id"]
        status = document["status"]
        if status == "deleted":
            raise DocumentProcessingError("DOCUMENT_NOT_FOUND", 404)
        if status not in {"registered", "failed"}:
            raise DocumentProcessingError("DOCUMENT_STATE_CONFLICT", 409)

        try:
            validate_upload_config(settings)
            stored = await save_upload_file(
                settings=settings,
                scoped_user=scoped_user,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                declared_content_type=document["content_type"],
                expected_size_bytes=document["size_bytes"],
                upload=upload,
            )
            uploaded = self.document_registry.update_for_processing(
                settings,
                scoped_user,
                knowledge_base_id,
                document_id,
                {
                    "status": "uploaded",
                    "storage_key": stored.storage_key,
                    "checksum_sha256": stored.checksum_sha256,
                    "uploaded_at": _now_from_record_timestamp(),
                    "error_code": None,
                },
            )
            if uploaded is None:
                raise DocumentProcessingError("DOCUMENT_NOT_FOUND", 404)
            self.document_registry.update_for_processing(
                settings,
                scoped_user,
                knowledge_base_id,
                document_id,
                {"status": "parsing", "error_code": None},
            )
            parsed = parse_document(stored.path, document["content_type"])
            chunker_name, chunks = chunk_text(settings, parsed.text)
            try:
                self.chunk_registry.replace_document_chunks(
                    settings,
                    scoped_user,
                    knowledge_base_id,
                    document_id,
                    chunks,
                )
            except ChunkRegistryError as exc:
                self._mark_failed(
                    settings,
                    scoped_user,
                    knowledge_base_id,
                    document_id,
                    "CHUNK_REGISTRY_FAILED",
                )
                raise DocumentProcessingError("CHUNK_REGISTRY_FAILED", 500) from exc

            updated = self.document_registry.update_for_processing(
                settings,
                scoped_user,
                knowledge_base_id,
                document_id,
                {
                    "status": "parsed",
                    "parser_name": parsed.parser_name,
                    "chunker_name": chunker_name,
                    "chunk_count": len(chunks),
                    "parsed_at": _now_from_record_timestamp(),
                    "error_code": None,
                },
            )
            if updated is None:
                raise DocumentProcessingError("DOCUMENT_NOT_FOUND", 404)
            return updated
        except FileStorageError as exc:
            self._mark_failed(
                settings,
                scoped_user,
                knowledge_base_id,
                document_id,
                exc.error_code,
            )
            raise DocumentProcessingError(exc.error_code, _storage_status(exc.error_code)) from exc
        except DocumentParseError as exc:
            self._mark_failed(
                settings,
                scoped_user,
                knowledge_base_id,
                document_id,
                exc.error_code,
            )
            raise DocumentProcessingError(exc.error_code, _parse_status(exc.error_code)) from exc
        except ChunkingError as exc:
            self._mark_failed(
                settings,
                scoped_user,
                knowledge_base_id,
                document_id,
                exc.error_code,
            )
            raise DocumentProcessingError(exc.error_code, 422) from exc
        except DocumentRegistryError as exc:
            raise DocumentProcessingError("DOCUMENT_REGISTRY_ERROR", 500) from exc

    def _mark_failed(
        self,
        settings: Settings,
        scoped_user: ScopedUser,
        knowledge_base_id: str,
        document_id: str,
        error_code: str,
    ) -> None:
        self.document_registry.update_for_processing(
            settings,
            scoped_user,
            knowledge_base_id,
            document_id,
            {"status": "failed", "error_code": error_code},
        )


def _storage_status(error_code: str) -> int:
    if error_code == "DOCUMENT_TOO_LARGE":
        return 413
    if error_code == "UNSUPPORTED_DOCUMENT_TYPE":
        return 415
    if error_code == "DOCUMENT_SIZE_MISMATCH":
        return 409
    if error_code in {"INVALID_RAG_UPLOAD_CONFIG", "INVALID_RAG_CHUNK_CONFIG"}:
        return 500
    return 500


def _parse_status(error_code: str) -> int:
    if error_code == "UNSUPPORTED_DOCUMENT_TYPE":
        return 415
    if error_code in {"INVALID_TEXT_ENCODING", "INVALID_DOCUMENT_CONTENT"}:
        return 422
    if error_code == "NO_EXTRACTABLE_TEXT":
        return 422
    if error_code == "ENCRYPTED_PDF_UNSUPPORTED":
        return 422
    return 500


def _now_from_record_timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
