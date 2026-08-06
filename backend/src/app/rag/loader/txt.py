import chardet
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

# 加载 TXT 文件，使用 chardet 自动探测编码
def load_txt(file_path: str) -> list[Document]:


    # 1. 读取文件原始字节
    with open(file_path, "rb") as f:
        raw_bytes = f.read()

    # 2. chardet 自动探测编码
    detected = chardet.detect(raw_bytes)
    encoding = detected.get("encoding") or "utf-8"

    # 3. 用探测到的编码加载，失败则兜底 UTF-8
    try:
        loader = TextLoader(file_path, encoding=encoding)
        return loader.load()
    except (UnicodeDecodeError, UnicodeError, LookupError):
        loader = TextLoader(file_path, encoding="utf-8")
        return loader.load()
