from __future__ import annotations

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from app.core.config import get_settings

# 索引名称
INDEX_NAME = "knowledge_chunks"

# 全局单例：ES 客户端
_es_client: Elasticsearch | None = None

# 获取 ES 索引客户端
def get_es_client() -> Elasticsearch:

    global _es_client
    if _es_client is None:
        settings = get_settings()
        _es_client = Elasticsearch(
            f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}",
        )
    return _es_client

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
def index_chunks(chunks: list[dict]) -> int:
    #没数据就直接返回 0。
    if not chunks:
        return 0

    # 确保文件夹存在（没有就建）
    ensure_index()

    #把每条数据打包成 ES 要求的格式。比如你有 100 个 chunk，就生成 100 个包：
    actions = [
        {
            "_index": INDEX_NAME,
            "_source": chunk,
        }
        for chunk in chunks
    ]

    #一次性全部发过去。bulk 就是批量操作——100 条数据打包成一个请求发过去，而不是发 100 次。企业数据量大必须用 bulk，否则慢死
    success, errors = bulk(get_es_client(), actions, refresh=True)

    if errors:
        # 部分失败了也不管，返回成功数。比如 100 条发了过去，98 条成功 2 条失败，返回 98。
        pass

    return success  #返回存进去了几条。

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
