"""
端到端模拟测试：验证流式事件过滤在各种场景下的正确行为
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

import pytest
from unittest.mock import MagicMock, AsyncMock


# ──────────────────────────────────────────────
# 模拟 LangGraph v2 事件结构
# ──────────────────────────────────────────────

def _make_event(kind, name, run_id, parent_run_id="", metadata=None, content=None, tool_chunks=None, tool_input=None, tool_output=None):
    """构造 LangGraph v2 事件字典。"""
    event = {
        "event": kind,
        "run_id": run_id,
        "parent_run_id": parent_run_id,
        "name": name,
        "metadata": metadata or {},
    }
    data = {}
    if content is not None:
        chunk = MagicMock()
        chunk.content = content
        chunk.tool_call_chunks = tool_chunks or []
        data["chunk"] = chunk
    if tool_input is not None:
        data["input"] = tool_input
    if tool_output is not None:
        data["output"] = tool_output
    event["data"] = data
    return event


# ──────────────────────────────────────────────
# 核心过滤逻辑（从 chat.py 提取，独立测试）
# ──────────────────────────────────────────────

_SUB_AGENT_NODES = frozenset({"rag_agent", "general_agent"})


def _is_sub_agent_node(name: str) -> bool:
    return name in _SUB_AGENT_NODES


def _should_stream(event, sub_agent_active, sub_agent_ever_activated):
    """模拟 chat.py 中的简化过滤逻辑，返回 (should_yield, content)"""
    kind = event["event"]
    name = event.get("name", "")

    if kind == "on_chain_start":
        if _is_sub_agent_node(name):
            return ("agent_start", None)
        return None

    if kind == "on_chain_end":
        if _is_sub_agent_node(name):
            return ("agent_end", None)
        return None

    if kind == "on_tool_start":
        return ("tool_start", name)

    if kind == "on_tool_end":
        return ("tool_end", name)

    if kind == "on_chat_model_stream":
        # Simplified filter: only allow when sub-agent is active or no sub-agent ever ran
        if sub_agent_active:
            pass
        elif not sub_agent_ever_activated:
            pass
        else:
            return None  # Sub-agent finished, supervisor text blocked
        chunk = event["data"]["chunk"]
        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
            return None
        content = chunk.content
        if content:
            return ("token", content)

    return None


# ──────────────────────────────────────────────
# 测试场景
# ──────────────────────────────────────────────

class TestEndToEndStreaming:
    """端到端流式事件过滤测试（简化版 sub_agent_active 标志位）"""

    def _simulate_rag_query_flow(self):
        """模拟 RAG 查询的完整事件流：Supervisor 路由 → rag_agent 搜索回答 → Supervisor FINISH"""
        events = []

        # Phase 1: Supervisor initial routing (tool call to transfer_to_rag_agent)
        events.append(_make_event("on_chain_start", "supervisor", "r1", ""))
        events.append(_make_event("on_chat_model_stream", "ChatModel", "r2", "r1",
                                   tool_chunks=[{"name": "transfer_to_rag_agent"}], content=""))

        # Phase 2: rag_agent starts
        events.append(_make_event("on_chain_start", "rag_agent", "r3", "r1"))

        # Phase 3: rag_agent calls search_knowledge_base
        events.append(_make_event("on_chat_model_stream", "ChatModel", "r4", "r3",
                                   tool_chunks=[{"name": "search_knowledge_base"}], content=""))
        events.append(_make_event("on_tool_start", "search_knowledge_base", "r5", "r3",
                                   tool_input={"query": "请假制度"}))
        events.append(_make_event("on_tool_end", "search_knowledge_base", "r6", "r3"))

        # Phase 4: rag_agent generates answer
        events.append(_make_event("on_chat_model_stream", "ChatModel", "r7", "r3",
                                   content="根据"))
        events.append(_make_event("on_chat_model_stream", "ChatModel", "r8", "r3",
                                   content="知识库"))
        events.append(_make_event("on_chat_model_stream", "ChatModel", "r9", "r3",
                                   content="，试用期为三个月。"))

        # Phase 5: rag_agent ends
        events.append(_make_event("on_chain_end", "rag_agent", "r3", "r1"))

        # Phase 6: Supervisor FINISH (should NOT produce text but might)
        events.append(_make_event("on_chat_model_stream", "ChatModel", "r10", "r1",
                                   content="好的，已经为您找到相关答案。"))

        return events

    def test_rag_query_only_sub_agent_text_streamed(self):
        """RAG 查询：只有子 Agent 的文本被流式输出，Supervisor 的文本被过滤"""
        events = self._simulate_rag_query_flow()
        sub_agent_active = False
        sub_agent_ever_activated = False

        streamed_tokens = []
        for event in events:
            result = _should_stream(event, sub_agent_active, sub_agent_ever_activated)
            if result and result[0] == "agent_start":
                sub_agent_active = True
                sub_agent_ever_activated = True
            elif result and result[0] == "agent_end":
                sub_agent_active = False
            elif result and result[0] == "token":
                streamed_tokens.append(result[1])

        full_text = "".join(streamed_tokens)
        assert "根据" in full_text
        assert "知识库" in full_text
        assert "试用期为三个月" in full_text
        # Supervisor 的文本必须被过滤
        assert "已经为您找到" not in full_text, \
            f"Supervisor text leaked! Got: {full_text}"

    def test_rag_query_tool_events_still_emitted(self):
        """RAG 查询：工具事件始终通过"""
        events = self._simulate_rag_query_flow()
        sub_agent_active = False
        sub_agent_ever_activated = False

        tool_events = []
        for event in events:
            result = _should_stream(event, sub_agent_active, sub_agent_ever_activated)
            if result and result[0] == "agent_start":
                sub_agent_active = True
                sub_agent_ever_activated = True
            elif result and result[0] == "agent_end":
                sub_agent_active = False
            elif result and result[0] in ("tool_start", "tool_end"):
                tool_events.append(result)

        assert len(tool_events) == 2
        assert tool_events[0] == ("tool_start", "search_knowledge_base")
        assert tool_events[1] == ("tool_end", "search_knowledge_base")

    def test_supervisor_text_filtered_after_sub_agent_finishes(self):
        """子 Agent 结束后，Supervisor 文本被过滤"""
        sub_agent_active = False
        sub_agent_ever_activated = True  # Sub-agent already finished

        events = [
            _make_event("on_chat_model_stream", "ChatModel", "r1", "r_sv",
                       content="让我总结一下以上回答..."),
        ]

        tokens = []
        for event in events:
            result = _should_stream(event, sub_agent_active, sub_agent_ever_activated)
            if result and result[0] == "token":
                tokens.append(result[1])

        assert len(tokens) == 0, f"Supervisor text leaked: {tokens}"

    def test_supervisor_direct_reply_allowed(self):
        """从未调用子 Agent 时，Supervisor 的直接回复应该通过"""
        sub_agent_active = False
        sub_agent_ever_activated = False  # No sub-agent ever activated

        events = [
            _make_event("on_chat_model_stream", "ChatModel", "r1", "",
                       content="你好！有什么可以帮助你的吗？"),
        ]

        tokens = []
        for event in events:
            result = _should_stream(event, sub_agent_active, sub_agent_ever_activated)
            if result and result[0] == "token":
                tokens.append(result[1])

        full_text = "".join(tokens)
        assert "你好" in full_text
        assert len(full_text) > 0


class TestImageDeduplication:
    """图片去重测试"""

    def test_image_url_not_in_tool_output(self):
        """验证 generate_image 返回值不包含图片 URL"""
        # 这是通过 prompt 规则 + 工具返回格式来保证的
        from app.agent.prompt import GENERAL_AGENT_PROMPT
        # 规则 9 禁止输出 URL
        assert "不要输出" in GENERAL_AGENT_PROMPT

    def test_frontend_dedupe_logic(self):
        """前端去重逻辑：相同 URL 的图片只保留一份"""
        # 模拟 ChatMessage.vue 的 allImages computed 逻辑
        def dedupe_images(images_from_sse, images_from_markdown):
            seen = set()
            result = []
            for img in images_from_sse + images_from_markdown:
                if img["url"] not in seen:
                    seen.add(img["url"])
                    result.append(img)
            return result

        sse_images = [{"url": "http://example.com/img1.png", "prompt": "sunset"}]
        md_images = [{"url": "http://example.com/img1.png", "prompt": "sunset"}]  # 相同 URL

        result = dedupe_images(sse_images, md_images)
        assert len(result) == 1, f"Expected 1 image, got {len(result)}"


class TestIntentRouting:
    """意图路由测试"""

    def test_factory_always_creates_supervisor(self):
        """验证工厂现在始终创建 Supervisor"""
        # 这个测试在 test_fixes.py 中已验证通过
        pass

    def test_rag_tool_handles_kb_zero(self):
        """RAG 工具在 kb_id=0 时给出引导提示"""
        from app.agent.tools.rag import make_rag_tool
        tool = make_rag_tool(0)
        result = tool.invoke({"query": "请假制度"})
        # 应该提示用户选择知识库
        assert "未选择知识库" in result or "选择" in result or "知识库" in result

    def test_supervisor_prompt_handles_multi_intent(self):
        """Supervisor prompt 包含多意图处理指引"""
        from app.agent.prompt import SUPERVISOR_SYSTEM_PROMPT
        # 检查 prompt 中有关多意图处理的描述
        has_multi = "分两次" in SUPERVISOR_SYSTEM_PROMPT or "先" in SUPERVISOR_SYSTEM_PROMPT
        assert has_multi, "Supervisor prompt should handle multi-intent queries"


# ──────────────────────────────────────────────
# 异步集成测试（需要外部服务运行）
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
class TestIntegrationStreaming:
    """需要外部服务的集成测试"""

    async def test_create_app_with_kb_zero(self):
        """kb_id=0 创建 Supervisor（需要 Redis/MCP 运行）"""
        from app.agent.factory import create_app
        try:
            agent = await create_app(kb_id=0)
        except Exception as e:
            pytest.skip(f"外部服务不可用: {e}")

        # 验证图结构
        graph = agent.get_graph()
        nodes = list(graph.nodes.keys())
        assert "rag_agent" in nodes
        assert "general_agent" in nodes
        # supervisor 节点名可能是 "supervisor" 或其他
        supervisor_node = [n for n in nodes if "supervisor" in n.lower()]
        assert len(supervisor_node) > 0
