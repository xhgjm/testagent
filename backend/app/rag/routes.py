from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.config import Settings, get_settings
from backend.app.platform.security import ScopedUser, get_scoped_user
from backend.app.rag.registry import (
    KnowledgeBaseRegistry,
    KnowledgeBaseRegistryError,
)
from backend.app.rag.schemas import (
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


def _safe_registry_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "KB_REGISTRY_ERROR",
            "message": "KnowledgeBase registry is unavailable.",
        },
    )


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KnowledgeBase not found.",
        )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KnowledgeBase not found.",
        )
    return KnowledgeBaseDeleteResponse(
        kb_id=kb_id,
        deleted=True,
        status="deleted",
    )
