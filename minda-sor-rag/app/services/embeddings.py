"""Embedding-function factory.

Returns a callable compatible with Chroma's embedding-function interface:
calling it with `list[str]` yields `list[list[float]]`. The same object is
passed to Chroma and also called directly by the Pinecone store.
"""

from __future__ import annotations

from typing import Any

from app.config import settings


def get_embedding_function() -> Any:
    provider = settings.EMBEDDING_PROVIDER

    if provider == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        kwargs: dict[str, Any] = {
            "api_key": settings.EMBEDDING_API_KEY or "no-key",
            "model_name": settings.EMBEDDING_MODEL,
        }
        if settings.EMBEDDING_BASE_URL:
            kwargs["api_base"] = settings.EMBEDDING_BASE_URL
        return OpenAIEmbeddingFunction(**kwargs)

    if provider == "sentence_transformers":
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        return SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL
        )

    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {provider!r}")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings using the configured provider."""
    fn = get_embedding_function()
    return [list(v) for v in fn(texts)]
