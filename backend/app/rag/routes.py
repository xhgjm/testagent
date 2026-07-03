from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.app.config import Settings, get_settings
from backend.app.platform.security import ScopedUser, get_scoped_user
from backend.app.rag.chunk_registry import ChunkRegistry, ChunkRegistryError
from backend.app.rag.document_registry import (
    DocumentRegistry,
    DocumentRegistryError,
)
from backend.app.rag.document_processing import (
    DocumentProcessingError,
    DocumentProcessingService,
)
from backend.app.rag.registry import (
    KnowledgeBaseRegistry,
    KnowledgeBaseRegistryError,
)
from backend.app.rag.schemas import (
    DocumentCreateRequest,
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDeleteResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)


router = APIRouter(
    prefix="/api/platform/knowledge-bases",
    tags=["platform-rag"],
)
_registry = KnowledgeBaseRegistry()
_document_registry = DocumentRegistry()
_chunk_registry = ChunkRegistry()
_document_processing_service = DocumentProcessingService(
    document_registry=_document_registry,
    chunk_registry=_chunk_registry,
)


def _safe_registry_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "KB_REGISTRY_ERROR",
            "message": "KnowledgeBase registry is unavailable.",
        },
    )


def _safe_document_registry_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "DOCUMENT_REGISTRY_ERROR",
            "message": "Document registry operation failed.",
        },
    )


def _safe_chunk_registry_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "CHUNK_REGISTRY_FAILED",
            "message": "Chunk registry operation failed.",
        },
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="KnowledgeBase not found.",
    )


def _document_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document not found.",
    )


def _ensure_active_knowledge_base(
    settings: Settings,
    scoped_user: ScopedUser,
    kb_id: str,
) -> None:
    try:
        item = _registry.get_for_owner(settings, scoped_user, kb_id)
    except KnowledgeBaseRegistryError as exc:
        raise _safe_registry_error() from exc
    if item is None:
        raise _not_found()


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    request: KnowledgeBaseCreateRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> KnowledgeBaseResponse:
    try:
        item = _registry.create(settings, scoped_user, request)
    except KnowledgeBaseRegistryError as exc:
        raise _safe_registry_error() from exc
    return KnowledgeBaseResponse(**item)


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> KnowledgeBaseListResponse:
    try:
        items = _registry.list_for_owner(settings, scoped_user)
    except KnowledgeBaseRegistryError as exc:
        raise _safe_registry_error() from exc
    responses = [KnowledgeBaseResponse(**item) for item in items]
    return KnowledgeBaseListResponse(items=responses, total=len(responses))


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: str,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> KnowledgeBaseResponse:
    try:
        item = _registry.get_for_owner(settings, scoped_user, kb_id)
    except KnowledgeBaseRegistryError as exc:
        raise _safe_registry_error() from exc
    if item is None:
        raise _not_found()
    return KnowledgeBaseResponse(**item)


@router.delete("/{kb_id}", response_model=KnowledgeBaseDeleteResponse)
async def delete_knowledge_base(
    kb_id: str,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> KnowledgeBaseDeleteResponse:
    try:
        item = _registry.delete_for_owner(settings, scoped_user, kb_id)
    except KnowledgeBaseRegistryError as exc:
        raise _safe_registry_error() from exc
    if item is None:
        raise _not_found()
    return KnowledgeBaseDeleteResponse(
        kb_id=kb_id,
        deleted=True,
        status="deleted",
    )


@router.post(
    "/{kb_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    kb_id: str,
    request: DocumentCreateRequest,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    _ensure_active_knowledge_base(settings, scoped_user, kb_id)
    try:
        item = _document_registry.create(settings, scoped_user, kb_id, request)
    except DocumentRegistryError as exc:
        raise _safe_document_registry_error() from exc
    return DocumentResponse(**item)


@router.get("/{kb_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    kb_id: str,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> DocumentListResponse:
    _ensure_active_knowledge_base(settings, scoped_user, kb_id)
    try:
        items = _document_registry.list_for_knowledge_base(settings, scoped_user, kb_id)
    except DocumentRegistryError as exc:
        raise _safe_document_registry_error() from exc
    documents = [DocumentResponse(**item) for item in items]
    return DocumentListResponse(documents=documents, total=len(documents))


@router.get("/{kb_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    kb_id: str,
    document_id: str,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    _ensure_active_knowledge_base(settings, scoped_user, kb_id)
    try:
        item = _document_registry.get_for_knowledge_base(
            settings,
            scoped_user,
            kb_id,
            document_id,
        )
    except DocumentRegistryError as exc:
        raise _safe_document_registry_error() from exc
    if item is None:
        raise _document_not_found()
    return DocumentResponse(**item)


@router.delete(
    "/{kb_id}/documents/{document_id}",
    response_model=DocumentDeleteResponse,
)
async def delete_document(
    kb_id: str,
    document_id: str,
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> DocumentDeleteResponse:
    _ensure_active_knowledge_base(settings, scoped_user, kb_id)
    try:
        item = _document_registry.delete_for_knowledge_base(
            settings,
            scoped_user,
            kb_id,
            document_id,
        )
    except DocumentRegistryError as exc:
        raise _safe_document_registry_error() from exc
    if item is None:
        raise _document_not_found()
    try:
        _chunk_registry.mark_document_chunks_deleted(
            settings,
            scoped_user,
            kb_id,
            document_id,
        )
    except ChunkRegistryError as exc:
        raise _safe_chunk_registry_error() from exc
    return DocumentDeleteResponse(
        document_id=document_id,
        knowledge_base_id=kb_id,
        deleted=True,
        status="deleted",
    )


@router.post(
    "/{kb_id}/documents/{document_id}/upload",
    response_model=DocumentResponse,
)
async def upload_document_file(
    kb_id: str,
    document_id: str,
    file: UploadFile = File(...),
    scoped_user: ScopedUser = Depends(get_scoped_user),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    _ensure_active_knowledge_base(settings, scoped_user, kb_id)
    try:
        document = _document_registry.get_for_knowledge_base(
            settings,
            scoped_user,
            kb_id,
            document_id,
        )
    except DocumentRegistryError as exc:
        raise _safe_document_registry_error() from exc
    if document is None:
        raise _document_not_found()
    try:
        updated = await _document_processing_service.upload_parse_and_chunk(
            settings,
            scoped_user,
            kb_id,
            document,
            file,
        )
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error_code": exc.error_code,
                "message": "Document upload, parsing, or chunking failed.",
            },
        ) from exc
    return DocumentResponse(**updated)
