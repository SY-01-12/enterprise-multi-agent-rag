from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import get_settings


llm_cache: dict[str, ChatOpenAI] = {}


def get_llm(model_name: str | None = None) -> ChatOpenAI:
    key = model_name or get_settings().BASE_MODEL
    if key not in llm_cache:
        settings = get_settings()
        llm_cache[key] = ChatOpenAI(
            model=key,
            api_key=settings.API_KEY,
            base_url=settings.BASE_URL,
            temperature=0.7,
        )
    return llm_cache[key]
