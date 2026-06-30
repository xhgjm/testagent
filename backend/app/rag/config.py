from pydantic import BaseModel

from backend.app.config import Settings


class RagServicePlan(BaseModel):
    enabled: bool = False
    qdrant_host: str
    qdrant_port: int
    blob_store_root: str
    notes: list[str]


def build_rag_service_plan(settings: Settings) -> RagServicePlan:
    """Describe future RAG Service integration points.

    TODO: Connect AgentScope RAG Service managers after confirming exact 2.0.3
    import paths:
    - QdrantStore
    - CollectionPerKbManager
    - Parser
    - Chunker
    - LocalBlobStore / OSS / S3 / MinIO
    - Async index worker
    """

    return RagServicePlan(
        enabled=False,
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        blob_store_root=settings.blob_store_root,
        notes=[
            "RAG is a platform capability, not the whole application.",
            "Knowledge bases must be isolated by tenant_id and permission policy.",
            "Document indexing should run asynchronously.",
        ],
    )
