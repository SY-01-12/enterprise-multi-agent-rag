"""RAG Chain 测试。

测试维度：
1. format_docs — 文档格式化单元测试
2. Prompt 渲染 — 验证模板变量填充正确
3. Prompt 规则验证 — 确保规则语意完整
4. RAG Chain 集成测试 — 需要 Ollama + Chroma 数据
"""

import pytest
from langchain_core.documents import Document as LangchainDocument

from app.services.retrieval_service import format_docs
from app.langchain_app.prompts.rag_prompt import get_rag_prompt, RAG_SYSTEM_TEMPLATE


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
        assert "\n\n" in result  # 空行分隔

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
# 2. Prompt 模板测试
# ══════════════════════════════════════════════════════

class TestRagPrompt:
    """测试 Prompt 模板的结构和规则。"""

    def test_prompt_structure(self):
        """Prompt 包含 system + human 两条消息（空历史时不产生额外消息）。"""
        prompt = get_rag_prompt()
        messages = prompt.format_messages(
            context="测试上下文",
            chat_history=[],
            question="测试问题？",
        )
        assert len(messages) == 2
        assert messages[0].type == "system"
        assert messages[1].type == "human"

    def test_context_injection(self):
        """context 变量被正确注入 system 消息。"""
        prompt = get_rag_prompt()
        messages = prompt.format_messages(
            context="员工试用期为三个月。",
            chat_history=[],
            question="试用期多久？",
        )
        assert "员工试用期为三个月" in messages[0].content
        assert "试用期多久？" == messages[1].content

    def test_rules_present(self):
        """Prompt 包含所有关键规则。"""
        rules_to_check = [
            "企业知识库智能助手",
            "基于知识库",
            "不知道就说不知道",
            "知识库中没有找到相关信息",
            "引用来源",
        ]
        for rule in rules_to_check:
            assert rule in RAG_SYSTEM_TEMPLATE, f"缺少规则: {rule}"

    def test_variables_in_template(self):
        """模板包含必需的变量占位符。"""
        assert "{context}" in RAG_SYSTEM_TEMPLATE
        # {question} 在 human message 中（prompt.messages[2]，因为 [1] 是 MessagesPlaceholder）
        prompt = get_rag_prompt()
        human_msg = prompt.messages[2].prompt.template
        assert "{question}" in human_msg


# ══════════════════════════════════════════════════════
# 3. RAG Chain 集成测试（需要 Ollama）
# ══════════════════════════════════════════════════════

@pytest.mark.integration
class TestRagChainIntegration:
    """需要 Ollama 运行且 Chroma 中有数据的集成测试。

    运行方式：
        pytest tests/test_rag_chain.py -v -m integration

    前提条件：
        - Ollama 服务已启动 (localhost:11434)
        - 已通过 POST /api/document/process/{id} 处理过文档
        - Chroma 中有 kb_1 的 collection
    """

    def test_ask_with_preset_context(self):
        """用预设 context 测试 LLM 是否按规则回答（不依赖 Chroma）。"""
        from app.langchain_app.prompts.rag_prompt import get_rag_prompt
        from app.langchain_app.llm.ollama import get_llm

        llm = get_llm()
        prompt = get_rag_prompt()
        messages = prompt.format_messages(
            context="[1] 来源: 员工手册.pdf\n员工试用期为三个月。",
            chat_history=[],
            question="员工试用期多久？",
        )
        response = llm.invoke(messages)
        answer = response.content

        # LLM 应该基于上下文回答
        assert "三个月" in answer, f"期望提到'三个月'，实际回答: {answer}"

    def test_unknown_question(self):
        """知识库无相关内容时，LLM 应回复'知识库中没有找到相关信息'。"""
        from app.langchain_app.prompts.rag_prompt import get_rag_prompt
        from app.langchain_app.llm.ollama import get_llm

        llm = get_llm()
        prompt = get_rag_prompt()
        messages = prompt.format_messages(
            context="（知识库中暂无相关内容）",
            chat_history=[],
            question="今天的天气怎么样？",
        )
        response = llm.invoke(messages)
        answer = response.content

        # LLM 应拒绝回答或明确告知不知道
        assert (
            "知识库中没有找到相关信息" in answer
            or "没有" in answer
            or "无法" in answer
            or "不知道" in answer
        ), f"期望拒绝编造，实际回答: {answer}"
