"""Model Studio HTTP client for embedding and reranking.

Uses ``httpx.AsyncClient`` to call the Model Studio API. All HTTP errors,
timeouts, and malformed responses are normalized into
:class:`RetrievalUnavailable`.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.retrieval.contracts import HybridEmbedding, RerankResult, RetrievalUnavailable

logger = logging.getLogger(__name__)

_EMBEDDING_PATH = "/services/embeddings/text-embedding/text-embedding"
_RERANK_PATH = "/reranks"
_BATCH_SIZE = 10
_DENSE_DIMENSION = 1024


class ModelStudioClient:
    """Async client for Model Studio embedding and rerank endpoints.

    Parameters
    ----------
    settings:
        Object with ``MODEL_STUDIO_BASE_URL``, ``MODEL_STUDIO_API_KEY``,
        ``MODEL_STUDIO_EMBEDDING_MODEL``, and ``MODEL_STUDIO_RERANK_MODEL``
        attributes.
    http:
        A pre-configured ``httpx.AsyncClient``.  Callers may inject one
        backed by ``httpx.MockTransport`` for testing.
    """

    def __init__(self, settings: Any, http: httpx.AsyncClient | None = None) -> None:
        self._base_url = str(settings.MODEL_STUDIO_BASE_URL).rstrip("/")
        self._rerank_base_url = self._compatible_api_base_url(self._base_url)
        self._api_key = settings.MODEL_STUDIO_API_KEY
        self._embedding_model = settings.MODEL_STUDIO_EMBEDDING_MODEL
        self._rerank_model = settings.MODEL_STUDIO_RERANK_MODEL
        self._http = http or httpx.AsyncClient()

    # -- Embedding -----------------------------------------------------------

    async def embed_documents(self, texts: list[str]) -> list[HybridEmbedding]:
        """Embed a list of texts as *documents* (batched by 10)."""
        all_embeddings: list[HybridEmbedding] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            all_embeddings.extend(await self._embed_batch(batch, text_type="document"))
        return all_embeddings

    async def embed_query(self, text: str) -> HybridEmbedding:
        """Embed a single text as a *query*."""
        results = await self._embed_batch([text], text_type="query")
        return results[0]

    # -- Rerank --------------------------------------------------------------

    async def rerank(self, query: str, documents: list[str]) -> list[RerankResult]:
        """Rerank *documents* with respect to *query*."""
        payload: dict[str, Any] = {
            "model": self._rerank_model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
            "instruct": "Retrieve novel canon passages relevant to the current writing task.",
        }
        data = await self._post(_RERANK_PATH, payload, base_url=self._rerank_base_url)
        try:
            results = data["results"]
            return [
                RerankResult(index=r["index"], score=r["relevance_score"])
                for r in results
            ]
        except (KeyError, TypeError, IndexError) as exc:
            logger.warning("Model Studio rerank returned unexpected payload: %s", type(exc).__name__)
            raise RetrievalUnavailable() from exc

    # -- Internals -----------------------------------------------------------

    async def _embed_batch(self, texts: list[str], *, text_type: str) -> list[HybridEmbedding]:
        payload: dict[str, Any] = {
            "model": self._embedding_model,
            "input": {"texts": texts},
            "parameters": {
                "dimension": _DENSE_DIMENSION,
                "output_type": "dense&sparse",
                "text_type": text_type,
            },
        }
        data = await self._post(_EMBEDDING_PATH, payload)
        try:
            raw_embeddings = data["output"]["embeddings"]
            result: list[HybridEmbedding] = []
            for emb in raw_embeddings:
                dense = emb["embedding"]
                sparse = emb["sparse_embedding"]
                if len(dense) != _DENSE_DIMENSION:
                    logger.warning(
                        "Model Studio returned unexpected dense dimension: expected=%d got=%d",
                        _DENSE_DIMENSION,
                        len(dense),
                    )
                    raise RetrievalUnavailable()
                sparse_indices, sparse_values = self._parse_sparse_embedding(sparse)
                result.append(
                    HybridEmbedding(
                        dense=dense,
                        sparse_indices=sparse_indices,
                        sparse_values=sparse_values,
                    )
                )
            return result
        except (KeyError, TypeError, IndexError) as exc:
            if isinstance(exc, RetrievalUnavailable):
                raise
            logger.warning("Model Studio embedding returned unexpected payload: %s", type(exc).__name__)
            raise RetrievalUnavailable() from exc

    @staticmethod
    def _parse_sparse_embedding(sparse: Any) -> tuple[list[int], list[float]]:
        """Normalize supported Model Studio sparse embedding response shapes.

        Older mock responses used parallel ``indices``/``values`` arrays, while
        Model Studio returns a list of ``index``/``token``/``value`` entries.
        The token text is informative only and is not required by Qdrant.
        """
        if isinstance(sparse, dict):
            indices = sparse["indices"]
            values = sparse["values"]
        elif isinstance(sparse, list):
            indices = [entry["index"] for entry in sparse]
            values = [entry["value"] for entry in sparse]
        else:
            raise TypeError("sparse_embedding must be an object or list")

        if (
            not isinstance(indices, list)
            or not isinstance(values, list)
            or len(indices) != len(values)
            or not all(isinstance(index, int) and not isinstance(index, bool) for index in indices)
            or not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values)
        ):
            raise TypeError("invalid sparse embedding values")

        return indices, [float(value) for value in values]

    @staticmethod
    def _compatible_api_base_url(base_url: str) -> str:
        """Derive the Model Studio qwen3-rerank API base from a DashScope URL."""
        parsed = urlsplit(base_url)
        return urlunsplit((parsed.scheme, parsed.netloc, "/compatible-api/v1", "", ""))

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        base_url: str | None = None,
    ) -> Any:
        """POST to Model Studio and return the parsed JSON body.

        Normalizes HTTP errors, timeouts, and malformed payloads into
        :class:`RetrievalUnavailable`.
        """
        url = f"{base_url or self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = await self._http.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning("Model Studio timeout: path=%s", path)
            raise RetrievalUnavailable() from exc
        except httpx.HTTPError as exc:
            logger.warning("Model Studio HTTP error: path=%s type=%s", path, type(exc).__name__)
            raise RetrievalUnavailable() from exc

        if response.status_code >= 400:
            logger.warning(
                "Model Studio request failed: status=%s path=%s",
                response.status_code,
                path,
            )
            raise RetrievalUnavailable()

        try:
            return response.json()
        except Exception as exc:
            logger.warning("Model Studio non-JSON response: type=%s", type(exc).__name__)
            raise RetrievalUnavailable() from exc
