"""Vector store abstraction.

Two implementations selected by VECTOR_DB env var:
  • ChromaStore   — embedded, local, persists to CHROMA_DIR
  • PineconeStore — cloud, serverless, requires PINECONE_API_KEY

Both expose the same three operations needed by the classifier:
  count()  → int
  add(documents, ids, metadatas) → None
  query(text, top_k) → list[str]   (returns the document strings, ranked)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.config import settings


@runtime_checkable
class VectorStore(Protocol):
    def count(self) -> int: ...
    def add(
        self,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None: ...
    def query(self, text: str, top_k: int) -> list[str]: ...


def get_vector_store() -> VectorStore:
    db = settings.VECTOR_DB
    if db == "chroma":
        return ChromaStore()
    if db == "pinecone":
        return PineconeStore()
    raise ValueError(f"Unknown VECTOR_DB: {db!r}")


class ChromaStore:
    def __init__(self) -> None:
        import chromadb

        from app.services.embeddings import get_embedding_function

        client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
        self._collection = client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            embedding_function=get_embedding_function(),
        )

    def count(self) -> int:
        return int(self._collection.count())

    def add(
        self,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self._collection.add(documents=documents, ids=ids, metadatas=metadatas)

    def query(self, text: str, top_k: int) -> list[str]:
        res = self._collection.query(query_texts=[text], n_results=top_k)
        docs = (res.get("documents") or [[]])[0]
        return list(docs)


class PineconeStore:
    def __init__(self) -> None:
        try:
            from pinecone import Pinecone, ServerlessSpec
        except ImportError as e:
            raise RuntimeError(
                "pinecone-client not installed. "
                "Run: pip install 'pinecone-client>=5.0.0'"
            ) from e

        if not settings.PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY is required when VECTOR_DB=pinecone")

        from app.services.embeddings import get_embedding_function

        self._embed = get_embedding_function()
        self._pc = Pinecone(api_key=settings.PINECONE_API_KEY)

        existing = {idx.name for idx in self._pc.list_indexes()}
        if settings.PINECONE_INDEX not in existing:
            self._pc.create_index(
                name=settings.PINECONE_INDEX,
                dimension=settings.PINECONE_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=settings.PINECONE_CLOUD,
                    region=settings.PINECONE_REGION,
                ),
            )
        self._index = self._pc.Index(settings.PINECONE_INDEX)

    def count(self) -> int:
        stats = self._index.describe_index_stats()
        return int(stats.get("total_vector_count", 0) or 0)

    def add(
        self,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        vectors = self._embed(documents)
        items = []
        for i, doc_id in enumerate(ids):
            md = dict(metadatas[i])
            md["text"] = documents[i]
            items.append(
                {"id": doc_id, "values": list(vectors[i]), "metadata": md}
            )
        self._index.upsert(vectors=items)

    def query(self, text: str, top_k: int) -> list[str]:
        vec = self._embed([text])[0]
        res = self._index.query(
            vector=list(vec), top_k=top_k, include_metadata=True
        )
        matches = res.get("matches") or []
        return [
            m["metadata"].get("text", "")
            for m in matches
            if m.get("metadata")
        ]
