import os

from langchain_core.documents import Document

from app.rag.loader.pdf import load_pdf
from app.rag.loader.txt import load_txt
from app.rag.loader.docx import load_docx
from app.rag.loader.excel import load_xlsx
from app.rag.loader.image import load_image
from app.utils.cleaner import clean_document_text

# 各格式对应的 Loader
LOADER_MAP = {
    "pdf": load_pdf,
    "docx": load_docx,
    "txt": load_txt,
    "xlsx": load_xlsx,
    "xlsm": load_xlsx,
    "jpg": load_image,
    "jpeg": load_image,
    "png": load_image,
    "gif": load_image,
    "bmp": load_image,
    "webp": load_image,
}


def load_document(file_path: str) -> list[Document]:
    """加载文档并统一清洗。"""
    suffix = os.path.splitext(file_path)[-1].lstrip(".")
    loader = LOADER_MAP.get(suffix)

    if not loader:
        raise ValueError(
            f"不支持的文件格式: .{suffix}，仅支持: {', '.join(LOADER_MAP.keys())}"
        )

    docs = loader(file_path)

    # 统一清洗：每篇文档过 clean_document_text
    cleaned = []
    for doc in docs:
        text = clean_document_text(doc.page_content)
        if not text.strip():
            continue
        cleaned.append(Document(page_content=text, metadata=doc.metadata))

    return cleaned
