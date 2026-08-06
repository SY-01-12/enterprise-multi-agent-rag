from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def split_documents(
    documents: list[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> list[Document]:
    if not documents:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n## ",   # Markdown H2 标题
            "\n### ",  # Markdown H3 标题
            "\n\n",    # 段落
            "\n",
            "。\n", "！\n", "？\n",
            "。", "！", "？",
            ". ", "! ", "? ",
            "；", ";",
            "，", ",",
            ""         # 兜底硬切
        ]
    )
    chunks = splitter.split_documents(documents)

    # 为每个 chunk 补充 chunk_index 元数据（按 source + page 分组编号）
    counter: dict[tuple[str, int], int] = {}

    for chunk in chunks:
        source = chunk.metadata.get("source", "unknown")
        page = chunk.metadata.get("page", 0)
        key = (source, page)
        chunk_index = counter.get(key, 0)
        chunk.metadata["chunk_index"] = chunk_index
        counter[key] = chunk_index + 1

    return chunks
