from __future__ import annotations

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from app.core.config import get_settings

# 索引名称
INDEX_NAME = "knowledge_chunks"

# 全局单例：ES 客户端
es_client: Elasticsearch | None = None

# 获取 ES 索引客户端
def get_es_client() -> Elasticsearch:

    global es_client
    if es_client is None:
        settings = get_settings()
        es_client = Elasticsearch(
            f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}",
            request_timeout=5,   # 请求超时 5 秒
            max_retries=0,       # 不重试，快速失败
        )
    return es_client

# 创建索引
def ensure_index() -> None:

    client = get_es_client()
    if not client.indices.exists(index=INDEX_NAME):
        client.indices.create(
            index=INDEX_NAME,
            body={
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "integer"},
                        "document_id": {"type": "integer"},
                        "content": {"type": "text"},
                    }
                }
            },
        )

# 索引内容  批量存数据。
def index_chunks(chunks: list[dict], document_id: int | None = None) -> int:
    #没数据就直接返回 0。
    if not chunks:
        return 0

    # 确保文件夹存在（没有就建）
    ensure_index()

    client = get_es_client()

    # 清理该文档的旧 ES 记录，避免重复数据膨胀
    doc_id = document_id or chunks[0].get("document_id")
    if doc_id is not None:
        try:
            client.delete_by_query(
                index=INDEX_NAME,
                # 找到 document_id 字段的值等于 doc_id 的所有记录，删掉它们
                body={"query": {"term": {"document_id": doc_id}}},
                refresh=True,
            )
        except Exception:
            pass  # 清理失败不阻塞索引（可能 ES 里还没有旧数据）

    #把每条数据打包成 ES 要求的格式
    actions = [
        {
            "_index": INDEX_NAME,
            "_id": f"{chunk.get('document_id', '0')}_{chunk.get('chunk_id', '0')}",
            "_source": chunk,
        }
        for chunk in chunks
    ]

    #一次性全部发过去。bulk 就是批量操作
    #bulk() 返回一个元组：(成功数量, 错误列表)
    success, _ = bulk(client, actions, refresh=True)
    return success

# 搜索内容
def search_content(query: str, size: int = 10) -> list[dict]:

    client = get_es_client()
    result = client.search(
        index=INDEX_NAME,
        body={
            "query": {
                "match": {
                    "content": query,
                }
            },
            "size": size,
        },
    )

    hits = result["hits"]["hits"]
    return [{"score": hit["_score"], **hit["_source"]} for hit in hits]
