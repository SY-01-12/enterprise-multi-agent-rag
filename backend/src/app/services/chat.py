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


async def ask_question_stream(
    db: AsyncSession, current_user: User,
    knowledge_base_id: int, question: str,
    session_id: int | None = None,
    model: str | None = None,
    mode: str | None = None,
):
    if session_id is None:
        safe_kb = None if knowledge_base_id == 0 else knowledge_base_id
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

    agent = await create_app(kb_id=knowledge_base_id, model_name=model,
        checkpointer=await get_async_checkpointer())

    config = {"configurable": {"thread_id": str(session_id), "user_id": current_user.id}}

    full_answer = ""
    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=question)], "user_id": current_user.id},
            config=config, version="v2",
        ):
            kind = event["event"]

            if kind == "on_tool_end" and event.get("name") == "generate_image":
                img_info = get_last_image()
                if img_info.get("url"):
                    yield ImageGenerated(url=img_info["url"],
                        prompt=img_info.get("prompt", "")).to_sse()
                    clear_last_image()

            if kind == "on_chat_model_stream":
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
