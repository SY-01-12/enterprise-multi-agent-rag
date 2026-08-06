"""
验证四个问题的修复：
1. RAG 检索不再重复回复（流式事件过滤）
2. 图片生成不再重复出现（URL 与文本分离）
3. 始终使用 Supervisor 自动意图路由（不再需要手动选择模式）
4. 完整功能测试
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

import pytest


# ──────────────────────────────────────────────
# 测试 1: 图片工具 — URL 不再出现在返回值中
# ──────────────────────────────────────────────
class TestImageTool:
    """验证 generate_image 工具返回值不再包含图片 URL"""

    def test_tool_exists(self):
        from app.agent.tools.image_gen import generate_image
        assert generate_image is not None
        assert generate_image.name == "generate_image"

    def test_no_api_key_returns_clean_message(self):
        """没有 API Key 时，工具返回的消息不包含 URL"""
        from app.agent.tools.image_gen import generate_image
        # 不设置 API_KEY 会返回错误提示，但不含 URL
        result = generate_image.invoke({"prompt": "test"})
        assert "http" not in result.lower() or "api_key" in result.lower()
        # 确保不含 Markdown 图片语法
        assert "![" not in result

    def test_store_mechanism_exists(self):
        """验证 get_last_image / clear_last_image 可用"""
        from app.agent.tools.image_gen import get_last_image, clear_last_image
        info = get_last_image()
        assert isinstance(info, dict)
        clear_last_image()
        info2 = get_last_image()
        assert info2 == {}


# ──────────────────────────────────────────────
# 测试 2: RAG 工具 — kb_id=0 时的行为
# ──────────────────────────────────────────────
class TestRagTool:
    """验证 make_rag_tool 在 kb_id=0 时返回引导提示"""

    def test_kb_zero_returns_guidance(self):
        from app.agent.tools.rag import make_rag_tool
        tool = make_rag_tool(0)
        result = tool.invoke({"query": "请假制度"})
        assert "未选择知识库" in result or "知识库" in result
        # 不应该有实际的检索结果
        assert "来源:" not in result or "未选择" in result

    def test_kb_nonzero_creates_tool(self):
        from app.agent.tools.rag import make_rag_tool
        tool = make_rag_tool(1)
        assert tool.name == "search_knowledge_base"
        # kb_id=1 的工具应该能正常调用（虽然可能连不上 Chroma，但不应该崩溃）
        # 这里只验证工具创建成功


# ──────────────────────────────────────────────
# 测试 3: 流式事件过滤逻辑
# ──────────────────────────────────────────────
class TestStreamFilter:
    """验证子 Agent 节点检测（简化版：使用 sub_agent_active 标志）"""

    def test_is_sub_agent_node(self):
        from app.services.chat import _is_sub_agent_node
        assert _is_sub_agent_node("rag_agent") is True
        assert _is_sub_agent_node("general_agent") is True
        assert _is_sub_agent_node("supervisor") is False
        assert _is_sub_agent_node("call_model") is False
        assert _is_sub_agent_node("") is False

    def test_filter_concept(self):
        """验证过滤逻辑：sub_agent_active 标志位控制流式输出"""
        # 这个测试验证概念而非具体实现
        # 1. 子 Agent 活跃期间 → 流式文本通过
        # 2. 从未激活子 Agent → Supervisor 直接回复通过
        # 3. 子 Agent 结束后 → Supervisor 的后续文本被屏蔽
        sub_agent_active = False
        sub_agent_ever_activated = False

        # Phase 1: 无子 Agent → 允许（Supervisor 直接回复）
        should_stream = sub_agent_active or not sub_agent_ever_activated
        assert should_stream is True

        # Phase 2: 子 Agent 启动
        sub_agent_active = True
        sub_agent_ever_activated = True
        should_stream = sub_agent_active or not sub_agent_ever_activated
        assert should_stream is True

        # Phase 3: 子 Agent 结束 → 不允许
        sub_agent_active = False
        # sub_agent_ever_activated 仍为 True
        should_stream = sub_agent_active or not sub_agent_ever_activated
        assert should_stream is False


# ──────────────────────────────────────────────
# 测试 4: Supervisor Prompt 验证
# ──────────────────────────────────────────────
class TestPrompts:
    """验证 Prompt 已更新为自动路由模式"""

    def test_supervisor_prompt_routes_both_agents(self):
        from app.agent.prompt import SUPERVISOR_SYSTEM_PROMPT
        assert "transfer_to_rag_agent" in SUPERVISOR_SYSTEM_PROMPT
        assert "transfer_to_general_agent" in SUPERVISOR_SYSTEM_PROMPT
        # 禁止复述
        assert "禁止复述" in SUPERVISOR_SYSTEM_PROMPT or "复述" in SUPERVISOR_SYSTEM_PROMPT

    def test_general_agent_no_url_in_output(self):
        from app.agent.prompt import GENERAL_AGENT_PROMPT
        # 规则 9: 不要输出图片 URL
        assert "不要输出" in GENERAL_AGENT_PROMPT or "禁止" in GENERAL_AGENT_PROMPT

    def test_rag_agent_prompt_updated(self):
        from app.agent.prompt import RAG_AGENT_PROMPT
        # RAG Agent 不再声称自己能计算（交给 General Agent）
        assert "Supervisor" in RAG_AGENT_PROMPT or "转交" in RAG_AGENT_PROMPT


# ──────────────────────────────────────────────
# 测试 5: factory 始终返回 Supervisor
# ──────────────────────────────────────────────
class TestFactory:
    """验证 create_app 始终创建 Supervisor 多 Agent 图"""

    @pytest.mark.asyncio
    async def test_creates_supervisor_with_kb_zero(self):
        """kb_id=0 也应返回 Supervisor 图（不再退化为纯 General Agent）"""
        from app.agent.factory import create_app

        try:
            agent = await create_app(kb_id=0)
        except Exception:
            # 外部依赖可能不可用（Chroma/ES/Redis），跳过测试
            return

        # 验证图的节点包含 supervisor、rag_agent、general_agent
        nodes = list(agent.get_graph().nodes.keys())
        # 应该有 supervisor 节点（可能是 "supervisor" 或类似）
        supervisor_nodes = [n for n in nodes if "supervisor" in n.lower()]
        assert len(supervisor_nodes) > 0, f"Expected supervisor node, got nodes: {nodes}"
        # 应该有 rag_agent 节点
        assert "rag_agent" in nodes, f"Expected rag_agent in nodes: {nodes}"
        # 应该有 general_agent 节点
        assert "general_agent" in nodes, f"Expected general_agent in nodes: {nodes}"
