from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings


@lru_cache(1)
def get_vision_llm() -> ChatOpenAI:
    """获取全局单例 Vision LLM（OCR / 图片理解专用，temperature=0）。"""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.OCR_MODEL,
        api_key=settings.API_KEY,
        base_url=settings.BASE_URL,
        temperature=0,
    )
