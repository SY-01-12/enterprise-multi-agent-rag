from operator import itemgetter

from app.langchain_app.llm.ollama import get_llm
from app.langchain_app.prompts.rag_prompt import get_rag_prompt
from app.langchain_app.vectorstores.chroma import get_langchain_chroma
from app.services.retrieval_service import format_docs


def create_rag_chain(kb_id: int):

    vectorstore = get_langchain_chroma(kb_id)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    rag_chain = (
        {
            # question : 利用问题 ---> retriever ---> 格式化
            "context": itemgetter("question") | retriever | format_docs,
            # question : 用户的原始问题
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_histor      y"),
        }
        | get_rag_prompt()
        | get_llm()
    )

    return rag_chain


#流式输出
def stream(kb_id: int, question: str, chat_history: list | None = None):

    chain = create_rag_chain(kb_id)
    for chunk in chain.stream({
        "question": question,
        "chat_history": chat_history or [],
    }):
        yield chunk.content

