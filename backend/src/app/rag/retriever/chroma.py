from __future__ import annotations

import chromadb
from langchain_chroma import Chroma

from app.core.config import get_settings
from app.embedding.dashscope import get_embedding_model

# 全局单例：Chroma HTTP 客户端
chroma_client: chromadb.HttpClient | None = None

# 获取 Chroma HTTP 客户端
def get_chroma_client() -> chromadb.HttpClient:
    global chroma_client
    if chroma_client is None:
        settings = get_settings()
        chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )
    return chroma_client

# 获取集合名称:  起名字 如： 知识库 ID=1 --> kb_1
def get_collection_name(knowledge_base_id: int) -> str:

    return f"kb_{knowledge_base_id}"

# 获取 LangChain Chroma
def get_langchain_chroma(knowledge_base_id: int) -> Chroma:
    client = get_chroma_client()
    embeddings = get_embedding_model()
    name = get_collection_name(knowledge_base_id)

    return Chroma(
        client=client,
        collection_name=name,
        embedding_function=embeddings,
    )
