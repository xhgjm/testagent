from dataclasses import dataclass
from pathlib import Path


class DocumentParseError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    parser_name: str
    metadata: dict[str, object]


def parse_document(path: Path, content_type: str) -> ParsedDocument:
    try:
        if content_type == "text/plain":
            return _parse_text(path, "plain_text_utf8")
        if content_type in {"text/markdown", "text/x-markdown"}:
            return _parse_text(path, "markdown_text_utf8")
        if content_type == "application/pdf":
            return _parse_pdf(path)
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("DOCUMENT_PARSE_FAILED") from exc
    raise DocumentParseError("UNSUPPORTED_DOCUMENT_TYPE")


def _parse_text(path: Path, parser_name: str) -> ParsedDocument:
    try:
        data = path.read_bytes()
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentParseError("INVALID_TEXT_ENCODING") from exc
    text = _normalize_text(text)
    if not text.strip():
        raise DocumentParseError("INVALID_DOCUMENT_CONTENT")
    return ParsedDocument(text=text, parser_name=parser_name, metadata={})


def _parse_pdf(path: Path) -> ParsedDocument:
    if not path.read_bytes().startswith(b"%PDF-"):
        raise DocumentParseError("UNSUPPORTED_DOCUMENT_TYPE")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentParseError("PDF_PARSER_UNAVAILABLE") from exc

    reader = PdfReader(str(path))
    if getattr(reader, "is_encrypted", False):
        raise DocumentParseError("ENCRYPTED_PDF_UNSUPPORTED")

    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = _normalize_text(text)
        if text.strip():
            pages.append(f"[Page {index}]\n{text.strip()}")

    if not pages:
        raise DocumentParseError("NO_EXTRACTABLE_TEXT")

    return ParsedDocument(
        text="\n\n".join(pages),
        parser_name="pypdf_text",
        metadata={"page_count": len(reader.pages)},
    )


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
