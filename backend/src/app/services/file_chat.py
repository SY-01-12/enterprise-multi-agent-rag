import os
import tempfile

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, SystemMessage

from app.models import User
from app.schema.chat import SessionCreated, TokenGenerated, StreamDone, StreamError
from app.rag.loader.factory import load_document
from app.llm import get_llm
from app.services.document import ALLOWED_EXTENSIONS
from app.services.history import create_session, save_message, get_session
from app.agent.prompt import FILE_CHAT_PROMPT

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_CONTENT_CHARS = 20000


class _FileError(Exception):
    """文件校验/解析错误，统一转为 SSE StreamError。"""


async def ask_file_stream(
    db: AsyncSession,
    current_user: User,
    file: UploadFile,
    question: str,
    session_id: int | None = None,
    model: str | None = None,
):
    # ── 1. 文件校验 + 解析 ──
    try:
        if not file.filename:
            raise _FileError("文件名为空")
        ext = os.path.splitext(file.filename)[-1].lstrip(".").lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise _FileError(f"不支持的文件格式: .{ext}")

        content_bytes = await file.read()
        if len(content_bytes) > MAX_FILE_SIZE:
            raise _FileError("文件过大，最大支持 10MB")

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            tmp.write(content_bytes)
            tmp_path = tmp.name
        try:
            docs = load_document(tmp_path)
        except ValueError as e:
            raise _FileError(str(e)) from e
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        if not docs:
            raise _FileError("文件内容为空或无法解析")

        file_content = "\n\n".join(d.page_content for d in docs)
        if len(file_content) > MAX_CONTENT_CHARS:
            file_content = file_content[:MAX_CONTENT_CHARS] + "\n\n...（内容过长，已截断）"

    except _FileError as e:
        yield StreamError(error=str(e)).to_sse()
        return

    # ── 2. 会话管理 ──
    if session_id is None:
        session = await create_session(
            db, user_id=current_user.id, knowledge_base_id=None,
            title=f"[文件] {file.filename}: {question[:30]}",
        )
        session_id = session.id
    else:
        await get_session(db, session_id, current_user.id)

    await save_message(db, session_id=session_id, role="user", content=question)
    yield SessionCreated(session_id=session_id).to_sse()

    # ── 3. LLM 流式生成 ──
    messages = [
        SystemMessage(content=FILE_CHAT_PROMPT.format(file_content=file_content)),
        HumanMessage(content=question),
    ]
    llm = get_llm(model_name=model)
    full_answer = ""
    try:
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if content:
                full_answer += content
                yield TokenGenerated(token=content).to_sse()
    except Exception as e:
        yield StreamError(error=str(e)).to_sse()
        return

    yield StreamDone().to_sse()
    if full_answer.strip():
        await save_message(db, session_id=session_id, role="assistant", content=full_answer)
