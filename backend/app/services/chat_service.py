"""聊天服务：SSE 流式问答编排。"""

from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

from app.models import User
from app.services.kb_service import get_knowledge_base_by_id
from app.langchain_app.chains.rag_chain import stream as rag_stream
from app.langchain_app.llm.ollama import get_llm
from app.langchain_app.prompts.rag_prompt import get_rag_prompt
from app.services.chat_history_service import (
    create_session,
    get_session_or_404,
    save_message,
    get_history,
)

# 通用对话 Prompt（不需要知识库，模型自由回答）
GENERAL_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是通义千问（Qwen），由阿里巴巴研发的大语言模型。请用中文友好地回答用户问题。"),
    ("human", "{question}"),
])


async def ask_question_stream(
    db: AsyncSession,
    current_user: User,
    knowledge_base_id: int,
    question: str,
    session_id: int | None = None,
):
    """SSE 流式 RAG 问答（异步生成器）。

    与非流式 ask_question 的前置步骤相同（权限检查、Session 管理、检索），
    但使用 LLM 的 stream 模式逐 token 输出 SSE 事件。

    Yields:
        str: SSE 格式的数据行，如 "data: 员工\n\n"
    """
    import json

    is_general = (knowledge_base_id == 0)

    # Step 1: 验证知识库（通用对话模式跳过）
    if not is_general:
        kb = await get_knowledge_base_by_id(knowledge_base_id, db)
        if not kb:
            yield f"data: {json.dumps({'error': '知识库不存在'})}\n\n"
            return
        if kb.owner_id != current_user.id:
            yield f"data: {json.dumps({'error': '无权限访问该知识库'})}\n\n"
            return

    # Step 2: Session 管理（通用对话 kb_id 为 NULL）
    session_kb_id = None if is_general else knowledge_base_id
    if session_id is None:
        title = question[:50]
        session = await create_session(
            db,
            user_id=current_user.id,
            knowledge_base_id=session_kb_id,
            title=title,
        )
        session_id = session.id
    else:
        session = await get_session_or_404(db, session_id, current_user.id)

    # Step 3: 保存用户消息
    await save_message(db, session_id=session_id, role="user", content=question)

    # Step 4: 构建 chat_history
    history_messages = await get_history(db, session_id)
    history_messages = history_messages[:-1]
    chat_history = [
        HumanMessage(content=msg.content)
        if msg.role == "user"
        else AIMessage(content=msg.content)
        for msg in history_messages
    ]

    # Step 5: 发送 session_id
    yield f"data: {json.dumps({'session_id': session_id})}\n\n"

    # Step 6: 流式生成
    full_answer = ""
    if is_general:
        # 通用对话：直接用 LLM，简洁 Prompt
        llm = get_llm()
        messages_in = GENERAL_CHAT_PROMPT.format_messages(question=question)
        for chunk in llm.stream(messages_in):
            full_answer += chunk.content
            yield f"data: {json.dumps({'token': chunk.content})}\n\n"
    else:
        # RAG 模式：检索 + LLM
        for token in rag_stream(
            kb_id=knowledge_base_id,
            question=question,
            chat_history=chat_history,
        ):
            full_answer += token
            yield f"data: {json.dumps({'token': token})}\n\n"

    # Step 7: 完成
    yield f"data: {json.dumps({'done': True})}\n\n"
    await save_message(db, session_id=session_id, role="assistant", content=full_answer)
