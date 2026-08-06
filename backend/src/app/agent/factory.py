from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from langgraph_supervisor import create_supervisor

from app.agent.prompt import (
    GENERAL_AGENT_PROMPT,
    RAG_AGENT_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
)
from app.agent.state import AgentState
from app.agent.memory.saver import get_async_checkpointer
from app.agent.memory.store import get_store
from app.llm import get_llm
from app.agent.tools import BASE_TOOLS, GENERAL_EXTRA_TOOLS, make_rag_tool
from app.agent.mcp.registry import get_mcp_tools


async def create_app(
    kb_id: int = 0,
    *,
    model_name: str | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
):
    """创建 Supervisor 多 Agent 图。始终返回 Supervisor，自动做意图路由。"""
    cp = checkpointer or await get_async_checkpointer()
    st = store or get_store()
    llm = get_llm(model_name=model_name)

    middleware = [
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 20),
        ),
    ]
    mcp_tools = await get_mcp_tools()

    # RAG Agent：知识库检索
    rag = create_agent(
        model=llm,
        state_schema=AgentState,
        checkpointer=cp,
        store=st,
        middleware=middleware,
        tools=[*BASE_TOOLS, make_rag_tool(kb_id)],
        system_prompt=RAG_AGENT_PROMPT,
        name="rag_agent",
    )

    # General Agent：图片/计算/时间/地图/记忆/创作
    general = create_agent(
        model=llm,
        state_schema=AgentState,
        checkpointer=cp,
        store=st,
        middleware=middleware,
        tools=[*BASE_TOOLS, *GENERAL_EXTRA_TOOLS, *mcp_tools],
        system_prompt=GENERAL_AGENT_PROMPT,
        name="general_agent",
    )

    return create_supervisor(
        agents=[rag, general],
        model=llm,
        prompt=SUPERVISOR_SYSTEM_PROMPT,
    ).compile(checkpointer=cp, store=st)
