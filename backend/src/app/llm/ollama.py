from __future__ import annotations

from langchain_ollama import ChatOllama

from app.core.config import get_settings

# 模型实例缓存
ollama_cache: dict[str, ChatOllama] = {}


def get_ollama_llm(model_name: str | None = None) -> ChatOllama:
    settings = get_settings()
    key = model_name or settings.OLLAMA_MODEL
    if not key:
        raise ValueError("未配置 OLLAMA_MODEL，请在 .env 中设置")
    if key not in ollama_cache:
        ollama_cache[key] = ChatOllama(
            model=key,
            base_url=f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}",
            temperature=0.7,
        )
    return ollama_cache[key]
