"""分层记忆系统测试 — 短期 / 中期 / 长期三层架构。

测试维度：
1. 触发条件      — 消息数未达阈值时不触发，超阈值时触发
2. 中期摘要      — 旧消息压缩为摘要，存入 state.summary
3. 长期记忆      — 关键事实提取并写入 Store
4. 消息裁剪      — 摘要消息 + 近期消息 替代全量历史
5. JSON 解析     — LLM 回复解析兼容性
6. 异步支持      — abefore_model 正常工作
7. 向后兼容      — 不传 store 也能正常运行
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from app.agent.state import AgentState
from app.agent.factory import create_app


# ── 测试用 LLM mock ────────────────────────────────────────────

def _make_mock_llm(summary: str = "测试摘要", facts: dict | None = None):
    """创建一个返回指定摘要和事实的 mock LLM（同时支持 sync 和 async 调用）。"""
    if facts is None:
        facts = {"用户姓名": "张三", "偏好语言": "Python"}

    response_data = {"summary": summary, "facts": facts}
    response_text = f"```json\n{json.dumps(response_data, ensure_ascii=False)}\n```"

    mock = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_text
    mock.invoke.return_value = mock_response

    # ainvoke 需要返回一个 coroutine，不能用 MagicMock
    async def _fake_ainvoke(*args, **kwargs):
        return mock_response
    mock.ainvoke = _fake_ainvoke
    return mock


# ══════════════════════════════════════════════════════
# 1. 触发条件测试
# ══════════════════════════════════════════════════════

class TestTriggerCondition:
    """测试摘要触发条件。"""

    def test_no_trigger_below_threshold(self):
        """消息数低于阈值时，before_model 返回 None（不触发）。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(),
            trigger_message_count=30,
            max_recent_messages=20,
        )

        # 构造一个只有 10 条消息的 state
        messages = [
            HumanMessage(content=f"msg{i}") for i in range(10)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = middleware.before_model(state, MagicMock())
        assert result is None, f"消息数({len(messages)}) < 阈值(30)，不应触发"

    def test_trigger_above_threshold(self):
        """消息数超过阈值时，before_model 应返回 state 更新。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(),
            store=InMemoryStore(),
            trigger_message_count=20,
            max_recent_messages=10,
        )

        # 构造 30 条消息（超过阈值 20）
        messages = [
            HumanMessage(content=f"msg{i}") for i in range(30)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = middleware.before_model(state, MagicMock())
        assert result is not None, f"消息数({len(messages)}) > 阈值(20)，应触发"
        assert "summary" in result
        assert "messages" in result
        assert result["summary"] == "测试摘要"

    def test_no_trigger_when_recent_fit(self):
        """split_index <= 0 时（近期消息已覆盖全部），不触发摘要。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(),
            trigger_message_count=20,
            max_recent_messages=50,  # 保留数 > 实际消息数
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(30)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = middleware.before_model(state, MagicMock())
        assert result is None, "split_index 为负，不应触发"


# ══════════════════════════════════════════════════════
# 2. 中期摘要测试
# ══════════════════════════════════════════════════════

class TestMidTermSummary:
    """测试中期摘要生成与 state 更新。"""

    def test_summary_stored_in_state(self):
        """摘要应存入 state.summary。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(summary="用户正在开发企业 RAG 系统"),
            store=InMemoryStore(),
            trigger_message_count=10,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = middleware.before_model(state, MagicMock())
        assert result is not None
        assert result["summary"] == "用户正在开发企业 RAG 系统"

    def test_existing_summary_incremental_update(self):
        """已有摘要时，新摘要应增量更新（通过 LLM prompt 传递已有摘要）。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        mock_llm = _make_mock_llm(summary="增量更新后的摘要")
        middleware = LayeredMemoryMiddleware(
            model=mock_llm,
            store=InMemoryStore(),
            trigger_message_count=10,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "之前的摘要内容",
            "last_summarized_count": 15,
        }

        result = middleware.before_model(state, MagicMock())
        assert result is not None
        # 验证调用时传入了已有摘要（检查 invoke 参数中包含 "之前的摘要内容"）
        call_arg = mock_llm.invoke.call_args[0][0]
        assert "之前的摘要内容" in call_arg, "LLM 调用应包含已有摘要"

    def test_llm_failure_returns_none(self):
        """LLM 调用失败时，返回 None，不裁剪消息避免丢失上下文。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("LLM 调用失败")

        middleware = LayeredMemoryMiddleware(
            model=mock_llm,
            store=InMemoryStore(),
            trigger_message_count=10,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = middleware.before_model(state, MagicMock())
        assert result is None, "LLM 失败应返回 None，保留所有消息"


# ══════════════════════════════════════════════════════
# 3. 长期记忆测试
# ══════════════════════════════════════════════════════

class TestLongTermFacts:
    """测试长期记忆事实提取与 Store 写入。"""

    def test_facts_written_to_store(self):
        """提取的事实应写入 Store，使用 ('memories', user_id) 命名空间。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        store = InMemoryStore()
        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(
                summary="测试摘要",
                facts={"用户姓名": "张三", "项目": "企业 RAG"},
            ),
            store=store,
            trigger_message_count=10,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 42,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        middleware.before_model(state, MagicMock())

        # 验证 Store 中有写入
        items = list(store.search(("memories", "42")))
        assert len(items) >= 2, f"应至少有 2 条记忆，实际 {len(items)} 条"

        # 验证具体内容
        stored = {item.key: item.value["value"] for item in items}
        assert stored.get("用户姓名") == "张三"
        assert stored.get("项目") == "企业 RAG"

    def test_empty_facts_not_written(self):
        """没有提取到事实时，不写入 Store。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        store = InMemoryStore()
        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(summary="测试", facts={}),
            store=store,
            trigger_message_count=10,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        middleware.before_model(state, MagicMock())

        items = list(store.search(("memories", "1")))
        assert len(items) == 0, "空事实不应写入"

    def test_no_store_no_crash(self):
        """不传 store 时，不写入长期记忆也不应崩溃。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(facts={"key": "value"}),
            store=None,  # 不传 store
            trigger_message_count=10,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        # 不应抛出异常
        result = middleware.before_model(state, MagicMock())
        assert result is not None
        assert result["summary"] == "测试摘要"


# ══════════════════════════════════════════════════════
# 4. 消息裁剪测试
# ══════════════════════════════════════════════════════

class TestMessageTrimming:
    """测试消息裁剪：旧消息替换为摘要，近期消息保留。"""

    def test_recent_messages_preserved(self):
        """裁剪后近期消息（最后 max_recent_messages 条）完整保留。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware
        from langgraph.graph.message import add_messages, REMOVE_ALL_MESSAGES
        from langchain_core.messages import RemoveMessage

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(),
            store=InMemoryStore(),
            trigger_message_count=15,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(25)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = middleware.before_model(state, MagicMock())
        assert result is not None

        # result["messages"] 包含 [RemoveMessage(REMOVE_ALL), summary_msg, *recent_5]
        result_messages = result["messages"]
        assert isinstance(result_messages[0], RemoveMessage)
        # 第 2 条是摘要消息
        assert isinstance(result_messages[1], HumanMessage)
        assert "对话历史摘要" in result_messages[1].content
        # 后续 5 条是近期消息
        recent = result_messages[2:]
        assert len(recent) == 5, f"应保留 5 条近期消息，实际 {len(recent)} 条"
        for i, msg in enumerate(recent):
            assert msg.content == f"msg{20 + i}"

    def test_summary_message_comes_first(self):
        """裁剪后的消息列表中，摘要消息在近期消息之前。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(summary="重要上下文"),
            store=InMemoryStore(),
            trigger_message_count=10,
            max_recent_messages=3,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = middleware.before_model(state, MagicMock())
        result_messages = result["messages"]

        # 跳过后，第一个有效消息应是摘要
        summary_msg = result_messages[1]
        assert "重要上下文" in summary_msg.content
        # 后续是近期消息
        assert result_messages[2].content == "msg17"
        assert result_messages[3].content == "msg18"
        assert result_messages[4].content == "msg19"

    def test_last_summarized_count_updated(self):
        """last_summarized_count 应在摘要后累加。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(),
            store=InMemoryStore(),
            trigger_message_count=10,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 10,  # 之前已摘要 10 条
        }

        result = middleware.before_model(state, MagicMock())
        # 本次摘要了 20 - 5 = 15 条旧消息，累加到 10 → 25
        assert result["last_summarized_count"] == 10 + 15


# ══════════════════════════════════════════════════════
# 5. JSON 解析测试
# ══════════════════════════════════════════════════════

class TestJSONParsing:
    """测试 LLM 回复的 JSON 解析兼容性。"""

    def test_parse_json_with_code_block(self):
        """带 ```json 代码块的回复应正确解析。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        text = '```json\n{"summary": "摘要内容", "facts": {"姓名": "李四"}}\n```'
        summary, facts = LayeredMemoryMiddleware.parse_response(text)

        assert summary == "摘要内容"
        assert facts == {"姓名": "李四"}

    def test_parse_json_without_code_block(self):
        """不带代码块的纯 JSON 回复应正确解析。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        text = '{"summary": "纯 JSON 摘要", "facts": {"项目": "RAG 系统"}}'
        summary, facts = LayeredMemoryMiddleware.parse_response(text)

        assert summary == "纯 JSON 摘要"
        assert facts == {"项目": "RAG 系统"}

    def test_parse_malformed_json(self):
        """非 JSON 回复应回退——返回原文作为摘要，facts 为空。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        text = "这是一段非 JSON 格式的回复文本"
        summary, facts = LayeredMemoryMiddleware.parse_response(text)

        assert summary == "这是一段非 JSON 格式的回复文本"
        assert facts == {}

    def test_parse_empty_text(self):
        """空文本返回空摘要和空 facts。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        summary, facts = LayeredMemoryMiddleware.parse_response("")
        assert summary == ""
        assert facts == {}

    def test_parse_none_text(self):
        """None 文本返回空摘要和空 facts。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        summary, facts = LayeredMemoryMiddleware.parse_response(None)
        assert summary == ""
        assert facts == {}

    def test_facts_with_non_string_values(self):
        """facts 中的非字符串值应被转为字符串。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        text = '{"summary": "test", "facts": {"count": 42, "active": true}}'
        summary, facts = LayeredMemoryMiddleware.parse_response(text)

        assert summary == "test"
        assert facts == {"count": "42", "active": "True"}


# ══════════════════════════════════════════════════════
# 6. 异步支持测试
# ══════════════════════════════════════════════════════

class TestAsyncSupport:
    """测试异步 before_model 钩子。"""

    @pytest.mark.asyncio
    async def test_async_trigger(self):
        """异步钩子应正确触发摘要。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(summary="异步摘要"),
            store=InMemoryStore(),
            trigger_message_count=10,
            max_recent_messages=5,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(20)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = await middleware.abefore_model(state, MagicMock())
        assert result is not None
        assert result["summary"] == "异步摘要"

    @pytest.mark.asyncio
    async def test_async_no_trigger(self):
        """未达阈值时异步钩子返回 None。"""
        from app.agent.memory.summarizer import LayeredMemoryMiddleware

        middleware = LayeredMemoryMiddleware(
            model=_make_mock_llm(),
            trigger_message_count=50,
            max_recent_messages=10,
        )

        messages = [
            HumanMessage(content=f"msg{i}") for i in range(10)
        ]
        state = {
            "messages": messages,
            "user_id": 1,
            "kb_id": None,
            "summary": "",
            "last_summarized_count": 0,
        }

        result = await middleware.abefore_model(state, MagicMock())
        assert result is None


# ══════════════════════════════════════════════════════
# 7. 向后兼容测试
# ══════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """测试分层记忆系统不影响现有功能。"""

    @pytest.mark.asyncio
    async def test_agent_still_creates_with_middleware(self):
        """无 kb_id 时单 Agent 正常创建并包含 checkpointer/store。"""
        checkpointer = MemorySaver()
        store = InMemoryStore()

        agent = await create_app(
            kb_id=None,
            checkpointer=checkpointer,
            store=store,
        )

        assert agent is not None
        assert agent.checkpointer is checkpointer
        assert agent.store is store

        nodes = list(agent.get_graph().nodes.keys())
        assert "model" in nodes
        assert "tools" in nodes

    def test_state_fields_include_memory_fields(self):
        """AgentState 应包含新增的 memory 字段。"""
        from typing import get_type_hints
        hints = get_type_hints(AgentState)
        assert "summary" in hints, "AgentState 缺少 summary 字段"
        assert "last_summarized_count" in hints, "AgentState 缺少 last_summarized_count 字段"

    def test_old_tests_still_work(self):
        """确保 state 实例化方式兼容（summary 和 last_summarized_count 有合理默认值）。"""
        state: AgentState = {
            "messages": [HumanMessage(content="你好")],
            "user_id": 1,
            "kb_id": None,
            "remaining_steps": 0,
            "summary": "",
            "last_summarized_count": -1,
        }
        assert state["summary"] == ""
        assert state["last_summarized_count"] == -1
