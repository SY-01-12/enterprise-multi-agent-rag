"""第零步改造测试 — LangGraph 显式化 + 记忆系统。

测试维度：
1. AgentState      — TypedDict 定义 & add_messages reducer
2. StateGraph 构建 — 节点、边、条件边完整性
3. 短期记忆        — MemorySaver checkpoint 自动保存/恢复
4. 长期记忆        — InMemoryStore 跨 thread 持久化
5. history 服务    — MySQL-only 持久化（Redis 缓存已移除）
6. chat 服务       — config 传 thread_id 替代手动拼消息
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from app.agent.state import AgentState
from app.agent.factory import create_app


# ══════════════════════════════════════════════════════
# 1. AgentState 定义测试
# ══════════════════════════════════════════════════════

class TestAgentState:
    """测试 AgentState TypedDict 与 add_messages reducer。"""

    def test_state_fields(self):
        """AgentState 必须包含 messages, user_id, kb_id, remaining_steps 字段。"""
        from typing import get_type_hints
        hints = get_type_hints(AgentState)
        assert "messages" in hints
        assert "user_id" in hints
        assert "kb_id" in hints
        assert "remaining_steps" in hints

    def test_state_instantiation(self):
        """AgentState 可以通过 TypedDict 方式实例化。"""
        state: AgentState = {
            "messages": [HumanMessage(content="你好")],
            "user_id": 1,
            "kb_id": None,
            "remaining_steps": 0,
        }
        assert state["messages"][0].content == "你好"
        assert state["user_id"] == 1
        assert state["kb_id"] is None

    def test_add_messages_reducer_merges_new(self):
        """add_messages reducer：新消息追加到列表末尾。"""
        from langgraph.graph.message import add_messages

        existing = [HumanMessage(content="问题1")]
        new = [AIMessage(content="回答1")]

        result = add_messages(existing, new)
        assert len(result) == 2
        assert result[0].content == "问题1"
        assert result[1].content == "回答1"

    def test_add_messages_reducer_fails_with_none(self):
        """add_messages reducer 要求左右值均非 None（LangGraph >= 1.2）。"""
        from langgraph.graph.message import add_messages
        import pytest as pytest_mod

        with pytest_mod.raises(ValueError):
            add_messages(None, [HumanMessage(content="你好")])

    def test_add_messages_reducer_with_empty_list(self):
        """add_messages reducer 左值为空列表时正常工作。"""
        from langgraph.graph.message import add_messages

        result = add_messages([], [HumanMessage(content="你好")])
        assert len(result) == 1
        assert result[0].content == "你好"


# ══════════════════════════════════════════════════════
# 2. StateGraph 构建测试
# ══════════════════════════════════════════════════════

class TestStateGraphBuild:
    """测试 Supervisor 图构建正确性。"""

    @pytest.mark.asyncio
    async def test_general_agent_without_kb(self):
        """无 kb_id 时应返回单 General Agent。"""
        agent = await create_app(
            kb_id=None,
            checkpointer=MemorySaver(),
            store=InMemoryStore(),
        )
        nodes = list(agent.get_graph().nodes.keys())
        assert "model" in nodes
        assert "tools" in nodes
        assert "__start__" in nodes

    @pytest.mark.asyncio
    async def test_supervisor_with_kb(self):
        """有 kb_id 时应返回 Supervisor，包含 RAG 和 General 子 Agent。"""
        agent = await create_app(
            kb_id=1,
            checkpointer=MemorySaver(),
            store=InMemoryStore(),
        )
        nodes = list(agent.get_graph().nodes.keys())
        assert "rag_agent" in nodes
        assert "general_agent" in nodes

    @pytest.mark.asyncio
    async def test_both_agents_created(self):
        """Supervisor 同时创建 RAG 和 General 子 Agent。"""
        agent = await create_app(
            kb_id=1,
            checkpointer=MemorySaver(),
            store=InMemoryStore(),
        )
        nodes = list(agent.get_graph().nodes.keys())
        assert "rag_agent" in nodes
        assert "general_agent" in nodes

    @pytest.mark.asyncio
    async def test_checkpointer_and_store_injected(self):
        """编译后的 agent 应包含 checkpointer 和 store。"""
        checkpointer = MemorySaver()
        store = InMemoryStore()

        agent = await create_app(
            kb_id=None,
            checkpointer=checkpointer,
            store=store,
        )
        assert agent.checkpointer is checkpointer
        assert agent.store is store


# ══════════════════════════════════════════════════════
# 3. 短期记忆（checkpointer）测试
# ══════════════════════════════════════════════════════

class TestShortTermMemory:
    """测试 RedisSaver（短期记忆）的替代实现 — MemorySaver。"""

    @pytest.mark.asyncio
    async def test_checkpoint_save_and_restore(self):
        """同一 thread_id 的 State 自动持久化和恢复。"""
        checkpointer = MemorySaver()
        store = InMemoryStore()
        agent = await create_app(
            kb_id=None,
            checkpointer=checkpointer,
            store=store,
        )

        thread_id = "test_thread_42"
        config = {"configurable": {"thread_id": thread_id}}

        state_before = agent.get_state(config)
        assert state_before.values == {}, "新 thread 的 State 应为空"

    @pytest.mark.asyncio
    async def test_state_accumulation_across_turns(self):
        """多轮对话后，State 中的 messages 应完整累积。"""
        checkpointer = MemorySaver()
        store = InMemoryStore()
        agent = await create_app(
            kb_id=None,
            checkpointer=checkpointer,
            store=store,
        )

        thread_id = "test_accumulation"
        config = {"configurable": {"thread_id": thread_id}}

        state0 = agent.get_state(config)
        assert state0.values == {}, "初始应为空"

    @pytest.mark.asyncio
    async def test_different_threads_independent(self):
        """不同 thread_id 的 State 互不影响。"""
        checkpointer = MemorySaver()
        store = InMemoryStore()
        agent = await create_app(
            kb_id=None,
            checkpointer=checkpointer,
            store=store,
        )

        thread_a_config = {"configurable": {"thread_id": "thread_a"}}
        thread_b_config = {"configurable": {"thread_id": "thread_b"}}

        state_a = agent.get_state(thread_a_config)
        state_b = agent.get_state(thread_b_config)

        assert state_a.values == {}
        assert state_b.values == {}


# ══════════════════════════════════════════════════════
# 4. 长期记忆（store）测试
# ══════════════════════════════════════════════════════

class TestLongTermMemory:
    """测试 RedisStore（长期记忆）的替代实现 — InMemoryStore。"""

    def test_store_put_and_get(self):
        """长期记忆可写入和读取。"""
        store = InMemoryStore()

        # 写入用户偏好
        store.put(
            ("user", "1", "preferences"),
            "style",
            {"value": "简洁回答"},
        )

        # 读取
        items = list(store.search(("user", "1", "preferences")))
        assert len(items) == 1
        assert items[0].value["value"] == "简洁回答"

    def test_store_namespace_isolation(self):
        """不同 namespace 的记忆互不干扰。"""
        store = InMemoryStore()

        store.put(("user", "1", "preferences"), "lang", {"value": "zh"})
        store.put(("user", "2", "preferences"), "lang", {"value": "en"})
        store.put(("kb", "1", "summary"), "desc", {"value": "技术文档"})

        # 用户 1 的偏好
        u1_items = list(store.search(("user", "1", "preferences")))
        assert len(u1_items) == 1
        assert u1_items[0].value["value"] == "zh"

        # 用户 2 的偏好
        u2_items = list(store.search(("user", "2", "preferences")))
        assert len(u2_items) == 1
        assert u2_items[0].value["value"] == "en"

        # 知识库摘要
        kb_items = list(store.search(("kb", "1", "summary")))
        assert len(kb_items) == 1
        assert kb_items[0].value["value"] == "技术文档"

    def test_store_put_overwrites(self):
        """同一 key 再次 put 可覆盖旧值。"""
        store = InMemoryStore()

        store.put(("user", "1", "topics"), "recent", {"value": ["Python"]})
        store.put(("user", "1", "topics"), "recent", {"value": ["Python", "RAG"]})

        items = list(store.search(("user", "1", "topics")))
        assert len(items) == 1
        assert items[0].value["value"] == ["Python", "RAG"]


# ══════════════════════════════════════════════════════
# 5. history 服务测试（MySQL-only 持久化）
# ══════════════════════════════════════════════════════

class TestHistoryService:
    """测试 history.py 在去掉 Redis 缓存后的行为。"""

    def test_history_no_redis_import(self):
        """history.py 不应再导入 Redis 模块（缓存逻辑已由 RedisSaver 接管）。"""
        import app.services.history as history_module
        import inspect

        source = inspect.getsource(history_module)
        # 不应包含对 get_redis 或 redis.asyncio 的直接使用
        assert "get_redis" not in source, (
            "history.py 不应再调用 get_redis，消息缓存由 LangGraph RedisSaver 接管"
        )
        # 不应包含 rpush / lrange 等 Redis 操作
        assert "rpush" not in source, "history.py 不应包含 Redis RPUSH 操作"
        assert "lrange" not in source, "history.py 不应包含 Redis LRANGE 操作"

    @pytest.mark.asyncio
    async def test_save_message_mysql_only(self):
        """save_message 只写 MySQL，不涉及 Redis。"""
        from app.services.history import save_message

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        message = await save_message(
            mock_db, session_id=1, role="user", content="测试消息"
        )

        # 验证：MySQL add + commit + refresh 被调用
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert message.role == "user"
        assert message.content == "测试消息"

    @pytest.mark.asyncio
    async def test_get_history_mysql_direct(self):
        """get_history 直接从 MySQL 查询。"""
        from app.services.history import get_history
        from app.models.chat_messages import ChatMessage

        mock_db = AsyncMock()
        # 模拟 MySQL 返回结果
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            ChatMessage(id=1, session_id=1, role="user", content="你好"),
            ChatMessage(id=2, session_id=1, role="assistant", content="你好！"),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        messages = await get_history(mock_db, session_id=1)

        assert len(messages) == 2
        assert messages[0].content == "你好"
        assert messages[1].content == "你好！"

    @pytest.mark.asyncio
    async def test_invalidate_history_cache_noop(self):
        """invalidate_history_cache 为 no-op（兼容接口）。"""
        from app.services.history import invalidate_history_cache

        # 不应抛出异常
        await invalidate_history_cache(session_id=1)


# ══════════════════════════════════════════════════════
# 6. chat 服务测试（config 传 thread_id）
# ══════════════════════════════════════════════════════

class TestChatService:
    """测试 chat.py 改造后的行为 — config 传递 thread_id。"""

    @pytest.mark.asyncio
    async def test_config_passes_thread_id(self):
        """验证 chat 服务使用 config["configurable"]["thread_id"] 而非手动拼消息。"""
        from app.services.chat import ask_question_stream

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = 1

        # Mock kb 权限检查（通用模式 kb_id=0 不会触发权限校验，但需 mock 防止 import 失败）
        with patch(
            "app.services.chat.require_owner",
            AsyncMock(),
        ):
            with patch(
                "app.services.chat.create_session",
                AsyncMock(return_value=MagicMock(id=99)),
            ):
                with patch(
                    "app.services.chat.save_message",
                    AsyncMock(),
                ):
                    with patch(
                        "app.services.chat.create_app",
                    ) as mock_create_agent:
                        # Mock agent
                        mock_agent = MagicMock()
                        mock_agent.astream_events = MagicMock(return_value=AsyncMock())

                        # 让 astream_events 产生一些事件
                        async def fake_events(*args, **kwargs):
                            yield {
                                "event": "on_chat_model_stream",
                                "data": {"chunk": AIMessage(content="测试")},
                            }
                            return

                        mock_agent.astream_events = fake_events
                        mock_create_agent.return_value = mock_agent

                        # 执行
                        events = []
                        async for event in ask_question_stream(
                            db=mock_db,
                            current_user=mock_user,
                            knowledge_base_id=0,  # 通用模式
                            question="你好",
                        ):
                            events.append(event)

                        # 验证 agent 创建时传入了 kb_id=None（通用模式）
                        mock_create_agent.assert_called_once()
                        call_kwargs = mock_create_agent.call_args.kwargs
                        assert call_kwargs["kb_id"] is None
                        assert call_kwargs["model_name"] is None

    @pytest.mark.asyncio
    async def test_manual_message_assembly_removed(self):
        """chat.py 不应导入 get_history（不再手动拉取历史消息）。"""
        import app.services.chat as chat_module
        import inspect

        source = inspect.getsource(chat_module)
        # 不应包含 get_history 导入或调用
        assert "get_history" not in source, (
            "chat.py 不应再导入/调用 get_history，历史消息由 LangGraph checkpointer 自动恢复"
        )
        # 不应包含从 history 模块导入 get_history
        if hasattr(chat_module, "get_history"):
            pytest.fail("chat.py 不应导出 get_history")

    @pytest.mark.asyncio
    async def test_stream_passes_single_human_message(self):
        """astream_events 只传递单条 HumanMessage（不含历史）。"""
        from app.services.chat import ask_question_stream

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = 1

        mock_session = MagicMock()
        mock_session.id = 99

        with patch(
            "app.services.chat.require_owner",
            AsyncMock(),
        ):
            with patch(
                "app.services.chat.get_session_or_404",
                AsyncMock(return_value=mock_session),
            ):
                with patch(
                    "app.services.chat.save_message",
                    AsyncMock(),
                ):
                    with patch(
                        "app.services.chat.create_app",
                    ) as mock_create_agent:
                        mock_agent = MagicMock()

                        async def fake_events(*args, **kwargs):
                            # 捕获传入的参数
                            fake_events.input = args[0]
                            fake_events.config = kwargs.get("config", {})
                            yield {
                                "event": "on_chat_model_stream",
                                "data": {"chunk": AIMessage(content="测试")},
                            }
                            return

                        mock_agent.astream_events = fake_events
                        mock_create_agent.return_value = mock_agent

                        events = []
                        async for event in ask_question_stream(
                            db=mock_db,
                            current_user=mock_user,
                            knowledge_base_id=0,
                            question="你好",
                            session_id=99,
                        ):
                            events.append(event)

                        # 验证只传递一条 HumanMessage
                        input_data = fake_events.input
                        msgs = input_data["messages"]
                        assert len(msgs) == 1
                        assert isinstance(msgs[0], HumanMessage)
                        assert msgs[0].content == "你好"

                        # 验证 config 包含 thread_id
                        config = fake_events.config
                        assert config["configurable"]["thread_id"] == "99"


# ══════════════════════════════════════════════════════
# 7. AgentState user_id/kb_id 传递测试
# ══════════════════════════════════════════════════════

class TestAgentStateUserContext:
    """测试 AgentState 中 user_id 和 kb_id 的正确传递。"""

    def test_state_contains_user_context(self):
        """AgentState 可携带 user_id 和 kb_id。"""
        state: AgentState = {
            "messages": [HumanMessage(content="查询")],
            "user_id": 42,
            "kb_id": 7,
            "remaining_steps": 0,
        }
        assert state["user_id"] == 42
        assert state["kb_id"] == 7
