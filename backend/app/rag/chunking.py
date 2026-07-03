import hashlib
from dataclasses import dataclass

from backend.app.config import Settings


class ChunkingError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class TextChunk:
    sequence: int
    text: str
    char_count: int
    checksum_sha256: str


def chunk_text(settings: Settings, text: str) -> tuple[str, list[TextChunk]]:
    chunk_size = settings.platform_rag_chunk_size
    overlap = settings.platform_rag_chunk_overlap
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ChunkingError("INVALID_RAG_CHUNK_CONFIG")

    normalized = _normalize_for_chunking(text)
    if not normalized:
        raise ChunkingError("INVALID_DOCUMENT_CONTENT")

    chunks: list[TextChunk] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = _find_boundary(normalized, start, end)
            if boundary > start:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(
                TextChunk(
                    sequence=len(chunks),
                    text=chunk,
                    char_count=len(chunk),
                    checksum_sha256=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                ),
            )
        if end >= len(normalized):
            break
        start = max(end - overlap, end if overlap == 0 else 0)
        if start >= end:
            start = end

    if not chunks:
        raise ChunkingError("INVALID_DOCUMENT_CONTENT")
    return "local_character_v1", chunks


def _normalize_for_chunking(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def _find_boundary(text: str, start: int, end: int) -> int:
    window = text[start:end]
    for marker in ("\n\n", "\n", ". ", "。"):
        index = window.rfind(marker)
        if index >= max(0, len(window) // 2):
            return start + index + len(marker)
    return end
