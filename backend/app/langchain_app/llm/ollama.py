"""LLM 管理模块。

当前使用阿里百炼（OpenAI 兼容 API），通过 langchain_openai.ChatOpenAI 接入。
切换其他模型只需修改此文件，业务代码无需改动。
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import get_settings

# 全局单例
_llm: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:

    global _llm
    if _llm is None:
        settings = get_settings()
        _llm = ChatOpenAI(
            model=settings.BASE_MODEL,
            api_key=settings.API_KEY,
            base_url=settings.BASE_URL,
            temperature=0.7,
        )
    return _llm
