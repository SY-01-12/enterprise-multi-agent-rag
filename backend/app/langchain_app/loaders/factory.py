import os

from langchain_core.documents import Document
from app.langchain_app.loaders.pdf_loader import load_pdf
from app.langchain_app.loaders.txt_loader import load_txt
from app.langchain_app.loaders.docx_loader import load_docx

# 各格式对应的 Loader
LOADER_MAP = {
    "pdf": load_pdf,
    "docx": load_docx,
    "txt": load_txt,
}


def load_document(file_path: str) -> list[Document]:
    suffix = os.path.splitext(file_path)[-1].lstrip(".")
    loader = LOADER_MAP.get(suffix)
    if not loader:
        raise ValueError(f"不支持的文件格式: .{suffix}，仅支持: {', '.join(LOADER_MAP.keys())}")
    return loader(file_path)