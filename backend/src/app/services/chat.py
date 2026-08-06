import logging
import traceback

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schema.chat import SessionCreated, TokenGenerated, StreamDone, StreamError, ImageGenerated
from app.agent.factory import create_app
from app.agent.memory.saver import get_async_checkpointer
from app.agent.tools.image_gen import get_last_image, clear_last_image
from app.services.history import create_session, save_message, get_session

logger = logging.getLogger(__name__)

_SUB_AGENT_NODES = frozenset({"rag_agent", "general_agent"})


async def ask_question_stream(
    db: AsyncSession, current_user: User,
    knowledge_base_id: int, question: str,
    session_id: int | None = None,
    model: str | None = None,
    mode: str | None = None,
):
    # ── 会话初始化 ──
    safe_kb = None if knowledge_base_id == 0 else knowledge_base_id
    if session_id is None:
        try:
            session = await create_session(db, user_id=current_user.id,
                knowledge_base_id=safe_kb, title=question[:50])
        except Exception:
            session = await create_session(db, user_id=current_user.id,
                knowledge_base_id=None, title=question[:50])
        session_id = session.id
    else:
        session = await get_session(db, session_id, current_user.id)
    await save_message(db, session_id=session_id, role="user", content=question)
    yield SessionCreated(session_id=session_id).to_sse()

    # ── 创建 Supervisor 多 Agent ──
    agent = await create_app(kb_id=knowledge_base_id, model_name=model,
        checkpointer=await get_async_checkpointer())

    config = {
        "configurable": {"thread_id": str(session_id), "user_id": current_user.id},
        "recursion_limit": 10,
    }

    sub_active = False     # 子 Agent 是否正在运行
    sub_ever = False       # 是否曾有子 Agent 运行过

    full_answer = ""
    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=question)], "user_id": current_user.id},
            config=config, version="v2",
        ):
            kind = event["event"]
            name = event.get("name", "")

            # ── 子 Agent 启动/结束 ──
            if kind == "on_chain_start" and name in _SUB_AGENT_NODES:
                sub_active = True
                sub_ever = True
            elif kind == "on_chain_end" and name in _SUB_AGENT_NODES:
                sub_active = False

            # ── 图片生成 ──
            if kind == "on_tool_end" and name == "generate_image":
                img_info = get_last_image()
                if img_info.get("url"):
                    yield ImageGenerated(url=img_info["url"],
                        prompt=img_info.get("prompt", "")).to_sse()
                    clear_last_image()

            # ── LLM 流式输出 ──
            if kind == "on_chat_model_stream":
                # 子 Agent 活跃 → 放行（真正的回答）
                # 子 Agent 从未运行 → 放行（Supervisor 简短问候）
                # 子 Agent 已结束 → 屏蔽（Supervisor 复述/路由指令）
                if not sub_active and (sub_ever or len(full_answer) >= 120):
                    continue

                chunk = event["data"]["chunk"]
                if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                    continue
                content = chunk.content
                if not content:
                    continue
                full_answer += content
                yield TokenGenerated(token=content).to_sse()

    except Exception as e:
        logger.error("Chat stream error: %s\n%s", type(e).__name__, traceback.format_exc())
        yield StreamError(error=f"{type(e).__name__}: {e}").to_sse()
        return

    yield StreamDone().to_sse()

    if full_answer.strip():
        await save_message(db, session_id=session_id, role="assistant", content=full_answer)
