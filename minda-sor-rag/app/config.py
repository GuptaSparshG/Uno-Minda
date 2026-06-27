"""Application configuration loaded from .env.

Two providers are pluggable:
  • LLM      — OpenAI (default) or any OpenAI-compatible endpoint
               (Ollama, vLLM, LM Studio, OpenRouter, Together, Anyscale, …)
  • Vector DB — Chroma (default, local, embedded) or Pinecone (cloud)

Legacy OPENAI_* env names are still honored for backwards compatibility.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ───────── LLM ─────────
    LLM_PROVIDER: Literal["openai"] = "openai"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    # ───────── Embeddings ─────────
    EMBEDDING_PROVIDER: Literal["openai", "sentence_transformers"] = "openai"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ───────── Vector DB ─────────
    VECTOR_DB: Literal["chroma", "pinecone"] = "chroma"
    RETRIEVAL_TOP_K: int = 3

    # Chroma (embedded, local)
    CHROMA_DIR: str = "storage/chroma_data"
    CHROMA_COLLECTION: str = "incose_iso_rules"

    # Pinecone (cloud)
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = "sor-incose-iso"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    PINECONE_DIMENSION: int = 1536

    # ───────── Legacy aliases (backwards-compat) ─────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = ""
    OPENAI_EMBEDDING_MODEL: str = ""

    # ───────── Server ─────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ───────── Storage ─────────
    UPLOAD_DIR: str = "storage/uploads"
    RESULTS_DIR: str = "storage/results"
    EXPORT_DIR: str = "storage/exports"

    # ───────── Pipeline ─────────
    MAX_PDF_SIZE_MB: int = 50
    BATCH_SIZE: int = 10
    MAX_PARALLEL_BATCHES: int = 6

    # ───────── Retention ─────────
    # Keep only the latest N jobs across all storage subdirs. Older jobs are
    # auto-pruned after each upload. Set to 0 to keep everything forever.
    MAX_RETAINED_JOBS: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def model_post_init(self, __context) -> None:
        # LLM key: prefer LLM_API_KEY, fall back to legacy OPENAI_API_KEY
        if not self.LLM_API_KEY:
            self.LLM_API_KEY = self.OPENAI_API_KEY
        # Embedding key: prefer EMBEDDING_API_KEY, then LLM_API_KEY, then legacy
        if not self.EMBEDDING_API_KEY:
            self.EMBEDDING_API_KEY = self.LLM_API_KEY or self.OPENAI_API_KEY
        # Legacy model-name aliases
        if self.OPENAI_MODEL and self.LLM_MODEL == "gpt-4o-mini":
            self.LLM_MODEL = self.OPENAI_MODEL
        if (
            self.OPENAI_EMBEDDING_MODEL
            and self.EMBEDDING_MODEL == "text-embedding-3-small"
        ):
            self.EMBEDDING_MODEL = self.OPENAI_EMBEDDING_MODEL


settings = Settings()
