from langchain_core.tools import tool

from app.rag.retriever.hybrid import hybrid_search
from app.utils.rag_utils import format_docs


def make_rag_tool(kb_id: int):
    """创建知识库检索工具。kb_id=0 时返回引导提示。"""
    if kb_id == 0:
        @tool
        def search_knowledge_base(query: str) -> str:
            """在知识库中检索相关文档。当用户的问题需要从企业知识库中查找信息时使用此工具。"""
            return "（当前未选择知识库。请在左侧下拉菜单中选择一个知识库后再提问，或选择「通用对话」模式进行非知识库类问答。）"
    else:
        @tool
        def search_knowledge_base(query: str) -> str:
            """在知识库中检索相关文档。当用户的问题需要从企业知识库中查找信息时使用此工具。"""

            docs = hybrid_search(kb_id=kb_id, query=query, top_k=3)
            return format_docs(docs)

    return search_knowledge_base
