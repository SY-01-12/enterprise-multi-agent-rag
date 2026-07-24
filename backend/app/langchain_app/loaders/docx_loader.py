from langchain_community.document_loaders import Docx2txtLoader
from langchain_core.documents import Document


def load_docx(file_path: str) -> list[Document]:
    loader = Docx2txtLoader(file_path)
    documents = loader.load()
    return documents
