"""LLM client factory.

Uses the OpenAI SDK with an optional `base_url` override so any
OpenAI-compatible endpoint works without code changes. Tested shapes:
  • OpenAI cloud           (LLM_BASE_URL unset)
  • Ollama local           (LLM_BASE_URL=http://localhost:11434/v1)
  • vLLM / LM Studio       (LLM_BASE_URL=http://localhost:8000/v1)
  • OpenRouter / Together  (LLM_BASE_URL=https://openrouter.ai/api/v1)
"""

from __future__ import annotations

from openai import OpenAI

from app.config import settings


def get_llm_client() -> OpenAI:
    kwargs: dict[str, str] = {"api_key": settings.LLM_API_KEY or "no-key"}
    if settings.LLM_BASE_URL:
        kwargs["base_url"] = settings.LLM_BASE_URL
    return OpenAI(**kwargs)
