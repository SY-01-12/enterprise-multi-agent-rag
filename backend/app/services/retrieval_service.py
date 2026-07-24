from langchain_core.documents import Document as LangchainDocument

from app.langchain_app.vectorstores.chroma import get_langchain_chroma
from app.langchain_app.search.elasticsearch import search_content


def retrieve_from_chroma(kb_id: int, query: str, top_k: int = 5) -> list[LangchainDocument]:

    vectorstore = get_langchain_chroma(kb_id)
    docs = vectorstore.similarity_search(query, k=top_k)
    return docs


def retrieve_from_es(query: str, size: int = 5) -> list[dict]:

    return search_content(query, size=size)


def retrieve(kb_id: int, query: str, top_k: int = 5) -> list[LangchainDocument]:

    # 1. Chroma 语义检索
    chroma_docs = retrieve_from_chroma(kb_id, query, top_k)

    # 2. ES 全文检索（ES 不可用时跳过，不影响主流程）
    es_docs = []
    try:
        es_results = retrieve_from_es(query, size=top_k)
        es_docs = [
            LangchainDocument(
                page_content=r["content"],
                metadata={"source": "ES 全文检索"},
            )
            for r in es_results
        ]
    except Exception:
        pass

    # 3. 去重合并：Chroma 优先，ES 补充不重复的内容
    seen = {doc.page_content for doc in chroma_docs}
    for doc in es_docs:
        if doc.page_content not in seen:
            chroma_docs.append(doc)
            seen.add(doc.page_content)

    return chroma_docs


def format_docs(docs: list[LangchainDocument]) -> str:

    if not docs:
        return "（知识库中暂无相关内容）"

    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知文档")
        parts.append(f"[{i}] 来源: {source}\n{doc.page_content}")

    return "\n\n".join(parts)
