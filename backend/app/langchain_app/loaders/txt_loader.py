from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

def load_txt(file_path: str) -> list[Document]:
    loader = TextLoader(file_path, encoding="utf-8")
    documents = loader.load()
    return documents