"""企业知识库问答 RAG Prompt 模板。

设计目标：
1. 角色定义 — 固定回答风格
2. 限制上下文 — 只能基于知识库内容回答
3. 不知道时处理 — 不编造，明确告知
4. 引用来源 — 企业场景需要可追溯
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

RAG_SYSTEM_TEMPLATE = """\
你是企业知识库智能助手，专门基于企业提供的知识库内容回答员工的问题。

## 回答规则（必须严格遵守）

1. **基于知识库**：你的所有回答必须严格基于下方【知识库内容】中的信息，不得使用你自身的训练数据或外部知识。

2. **不知道就说不知道**：如果【知识库内容】中没有包含回答该问题所需的信息，你必须明确回复：
   "知识库中没有找到相关信息。" 不要尝试猜测、推理或编造答案。

3. **引用来源**：回答时注明信息来源（文档名），让用户知道答案的出处。

4. **简洁准确**：回答简洁明了，使用中文。如果知识库内容足以回答，直接给出答案。

## 知识库内容
{context}

## 对话历史
下面是用户之前的对话记录，帮助你理解上下文。如果用户当前问题指代不明确（如"多久"、"什么意思"），请结合对话历史理解用户意图。"""


def get_rag_prompt() -> ChatPromptTemplate:
    """获取 RAG 问答 Prompt 模板。

    变量：
        context      — 从知识库检索到的文档内容（已格式化）
        chat_history — 历史对话消息列表（HumanMessage / AIMessage）
        question     — 用户当前问题

    Returns:
        ChatPromptTemplate: system(规则+context) + history + human(question)
    """
    return ChatPromptTemplate.from_messages(
        [
            ("system", RAG_SYSTEM_TEMPLATE),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
