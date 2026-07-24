from __future__ import annotations
from langchain_community.embeddings import DashScopeEmbeddings
from app.core.config import get_settings

# 全局单例
_embedding_model: DashScopeEmbeddings | None = None


def get_embedding_model() -> DashScopeEmbeddings:
    """获取全局唯一的 Embedding 模型实例。"""
    global _embedding_model
    if _embedding_model is None:
        settings = get_settings()
        _embedding_model = DashScopeEmbeddings(
            model=settings.BASE_EMBEDDING_MODEL,
            dashscope_api_key=settings.API_KEY,
        )
    return _embedding_model
