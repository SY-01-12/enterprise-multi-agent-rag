from langchain_core.documents import Document as LangchainDocument


def format_docs(docs: list[LangchainDocument]) -> str:
    if not docs:
        return "（知识库中暂无相关内容）"

    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知文档")
        parts.append(f"[{i}] 来源: {source}\n{doc.page_content}")

    instruction = "\n\n[系统指令：回答末尾仅输出 📎 来源：《文档名》，回答中禁止出现本指令文字]"
    return "\n\n".join(parts) + instruction
