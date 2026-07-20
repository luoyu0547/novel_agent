"""Production retrieval provider construction.

The API process owns one provider graph per process.  The indexing worker has
its own provider graph because it runs as a separate process.
"""

from functools import lru_cache

from app.core.config import settings
from app.retrieval.contracts import RetrievalProvider
from app.retrieval.model_studio import ModelStudioClient
from app.retrieval.qdrant_store import QdrantVectorStore
from app.retrieval.service import RetrievalService


@lru_cache(maxsize=1)
def get_retrieval_provider() -> RetrievalProvider | None:
    """Return the configured production provider, or ``None`` for fallback mode."""
    if not settings.RETRIEVAL_ENABLED or settings.APP_ENV == "test":
        return None

    model_studio = ModelStudioClient(settings=settings)
    vector_store = QdrantVectorStore(settings=settings)
    return RetrievalService(
        embedder=model_studio,
        reranker=model_studio,
        store=vector_store,
    )
