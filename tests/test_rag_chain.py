"""RAG & Agent 测试。

测试维度：
1. format_docs — 文档格式化单元测试
2. Agent Prompt — 验证 prompt 规则语意完整
3. Agent 集成测试 — 需要 Ollama + Chroma 数据
"""

import pytest
from langchain_core.documents import Document as LangchainDocument

from app.utils.rag_utils import format_docs
from app.agent.prompt import RAG_AGENT_PROMPT, GENERAL_AGENT_PROMPT


# ══════════════════════════════════════════════════════
# 1. format_docs 单元测试
# ══════════════════════════════════════════════════════

class TestFormatDocs:
    """测试文档格式化函数。"""

    def test_format_single_doc(self):
        """单文档：包含来源和内容。"""
        docs = [
            LangchainDocument(
                page_content="员工试用期为三个月。",
                metadata={"source": "员工手册.pdf"},
            )
        ]
        result = format_docs(docs)
        assert "员工手册.pdf" in result
        assert "员工试用期为三个月" in result
        assert result.startswith("[1]")

    def test_format_multiple_docs(self):
        """多文档：编号递增，空行分隔。"""
        docs = [
            LangchainDocument(page_content="内容A", metadata={"source": "文档A.pdf"}),
            LangchainDocument(page_content="内容B", metadata={"source": "文档B.pdf"}),
        ]
        result = format_docs(docs)
        assert "[1]" in result
        assert "[2]" in result
        assert "内容A" in result
        assert "内容B" in result
        assert "\n\n" in result

    def test_format_empty_docs(self):
        """空文档列表：返回提示语。"""
        result = format_docs([])
        assert "暂无相关内容" in result

    def test_format_doc_no_source(self):
        """文档无 source 元数据：使用默认值。"""
        docs = [LangchainDocument(page_content="测试内容", metadata={})]
        result = format_docs(docs)
        assert "未知文档" in result
        assert "测试内容" in result


# ══════════════════════════════════════════════════════
# 2. Agent Prompt 规则验证
# ══════════════════════════════════════════════════════

class TestAgentPrompt:
    """测试 Agent Prompt 包含所有必要规则。"""

    def test_rag_prompt_rules(self):
        """RAG 模式 prompt 包含关键规则。"""
        rules = [
            "search_knowledge_base",
            "检索",
            "知识库",
            "calculator",
            "current_time",
            "用中文简洁回答",
        ]
        for rule in rules:
            assert rule in RAG_AGENT_PROMPT, f"RAG prompt 缺少规则: {rule}"

    def test_general_prompt_rules(self):
        """通用模式 prompt 包含关键规则，且不涉及知识库检索。"""
        rules = [
            "calculator",
            "current_time",
            "无法访问企业知识库",
            "知识库检索",
        ]
        for rule in rules:
            assert rule in GENERAL_AGENT_PROMPT, f"General prompt 缺少规则: {rule}"

    def test_general_prompt_no_rag_tool(self):
        """通用模式 prompt 不提及 search_knowledge_base（工具不存在）。"""
        assert "search_knowledge_base" not in GENERAL_AGENT_PROMPT

    def test_rag_prompt_has_rag_tool(self):
        """RAG 模式 prompt 提及 search_knowledge_base。"""
        assert "search_knowledge_base" in RAG_AGENT_PROMPT


# ══════════════════════════════════════════════════════
# 3. Agent 集成测试（需要 Ollama）
# ══════════════════════════════════════════════════════

@pytest.mark.integration
class TestAgentIntegration:
    """需要 Ollama 运行的集成测试。

    运行方式：
        pytest tests/test_rag_chain.py -v -m integration

    前提条件：
        - Ollama 服务已启动 (localhost:11434)
        - 已通过 POST /api/document/process/{id} 处理过文档
        - Chroma 中有 kb_1 的 collection
    """

    @pytest.mark.asyncio
    async def test_supervisor_creates(self):
        """验证 Supervisor Agent 可创建。"""
        from app.agent.factory import create_app

        agent = await create_app(kb_id=1)
        assert agent is not None
        nodes = list(agent.get_graph().nodes.keys())
        assert "rag_agent" in nodes
        assert "general_agent" in nodes
