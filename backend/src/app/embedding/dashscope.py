from __future__ import annotations
from langchain_community.embeddings import DashScopeEmbeddings
from app.core.config import get_settings

# 全局单例
embedding_model: DashScopeEmbeddings | None = None

# 获取 embedding 模型
def get_embedding_model() -> DashScopeEmbeddings:

    global embedding_model
    if embedding_model is None:
        settings = get_settings()
        embedding_model = DashScopeEmbeddings(
            model=settings.BASE_EMBEDDING_MODEL,
            dashscope_api_key=settings.API_KEY,
        )
    return embedding_model
