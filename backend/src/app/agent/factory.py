from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from app.agent.state import AgentState
from app.agent.memory.saver import get_async_checkpointer
from app.agent.memory.store import get_store
from app.llm import get_llm
from app.agent.tools import BASE_TOOLS, GENERAL_EXTRA_TOOLS, make_rag_tool
from app.agent.mcp.registry import get_mcp_tools

UNIFIED_PROMPT = """你是企业 AI 助手，具备以下全部能力：

- search_knowledge_base：在企业知识库中检索文档内容
- generate_image：根据文字描述生成图片
- calculator：执行数学计算
- current_time：获取当前日期时间
- remember / recall / forget：管理用户跨会话记忆
- 文案写作、翻译、代码生成、地图搜索等

规则：
1. 知识库/制度/文档问题 → 先调用 search_knowledge_base 检索再回答，引用来源（📎 来源：《文档名》）
2. 图片生成 → 调用 generate_image，生成后简短告知即可，不输出 URL
3. 计算问题 → 调用 calculator
4. 时间问题 → 调用 current_time
5. 用户分享个人信息 → 调用 remember 记下来
6. 多任务问题逐步处理，全部完成后一次回复即可
7. 用中文简洁回答"""


async def create_app(
    kb_id: int = 0,
    *,
    model_name: str | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
):
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

    return create_agent(
        model=llm,
        state_schema=AgentState,
        checkpointer=cp,
        store=st,
        middleware=middleware,
        tools=[*BASE_TOOLS, make_rag_tool(kb_id), *GENERAL_EXTRA_TOOLS, *mcp_tools],
        system_prompt=UNIFIED_PROMPT,
        name="assistant",
    )
