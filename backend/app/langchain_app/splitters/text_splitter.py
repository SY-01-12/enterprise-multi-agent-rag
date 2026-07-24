from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def split_documents(
    documents: list[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[Document]:

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = splitter.split_documents(documents)

    # 为每个 chunk 补充 chunk_index 元数据
    # 按 source + page 分组计数
    # [str,int]: (文件名,页码)  int: 计数器 表示 内容来源与原文第几页的第几块位置
    counter: dict[tuple[str, int], int] = {}
    for chunk in chunks:
        #读取这个 chunk 来自哪个文件、哪一页。
        source = chunk.metadata.get("source", "unknown")
        page = chunk.metadata.get("page", 0)

        #拼一个唯一标记，比如 ("员工手册.pdf", 1) 表示"员工手册第1页"。
        key = (source, page)

        #查表：这一页已经编到几号了？第一次遇到就是 0。
        chunk_index = counter.get(key, 0)

        # 给这个 chunk 打上编号。
        chunk.metadata["chunk_index"] = chunk_index

        #编号 +1，等着给同一页的下一个 chunk 用。
        counter[key] = chunk_index + 1

    return chunks
