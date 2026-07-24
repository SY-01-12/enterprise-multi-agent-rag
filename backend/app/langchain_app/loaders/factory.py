import os

from langchain_core.documents import Document
from app.langchain_app.loaders.pdf_loader import load_pdf
from app.langchain_app.loaders.txt_loader import load_txt
from app.langchain_app.loaders.docx_loader import load_docx


def load_document(file_path: str) -> list[Document]:
    # 判断文件类型
    suffix = os.path.splitext(file_path)[-1]

    #根据类型 加载不同的加载器
    if suffix == ".pdf":
        return load_pdf(file_path)
    elif suffix == ".docx":
        return load_docx(file_path)
    elif suffix == ".txt":
        return load_txt(file_path)

    