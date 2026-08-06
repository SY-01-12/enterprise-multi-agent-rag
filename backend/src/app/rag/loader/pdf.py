from __future__ import annotations

import logging

import fitz
from langchain_core.documents import Document

from app.utils.cleaner import dedup_repeated_lines, filter_noise_pages
from app.utils.ocr import ocr_image

logger = logging.getLogger(__name__)


def load_pdf(file_path: str) -> list[Document]:
    doc = fitz.open(file_path)

    # 逐页提取文本
    pages_text: list[str] = []
    for page in doc:
        text = page.get_text()
        pages_text.append(text)

    # 检测扫描页并 OCR
    ocr_blank_pages(doc, pages_text)

    doc.close()

    if not pages_text:
        return []

    # 去页眉页脚 + 过滤噪声页
    pages_text = dedup_repeated_lines(pages_text)
    pages_text = filter_noise_pages(pages_text)

    # 重建 Document 列表
    cleaned: list[Document] = []
    for i, text in enumerate(pages_text):
        if not text.strip():
            continue
        cleaned.append(Document(
            page_content=text,
            metadata={"source": file_path, "page": i},
        ))

    return cleaned


def ocr_blank_pages(doc: fitz.Document, pages_text: list[str]) -> None:
    """对空白页及有嵌入图片的扫描页调用 Vision LLM 进行 OCR（原地修改 pages_text）。

    识别策略：
    1. 纯空白页 — 直接判定为扫描页
    2. ``page.get_textpage().extractBLOCKS()`` 检测嵌入图片 + 文字量 < 80 字符
       — 判定为扫描页（文字层是 OCR 残留/乱码），用 Vision LLM 重识别
    """
    ocr_candidates: list[int] = []

    for i, text in enumerate(pages_text):
        # 条件一：纯空白页 → 必然是扫描页
        if not text.strip():
            ocr_candidates.append(i)
            continue

        # 条件二：有嵌入图片 + 文字层极度稀疏 → 扫描页残留文字层
        page = doc[i]
        blocks = page.get_textpage().extractBLOCKS()
        has_image = any(b[-1] == 1 for b in blocks)               # block_type=1 → 图片
        if not has_image:
            continue

        text_chars = sum(len(str(b[4])) for b in blocks if b[-1] == 0)  # block_type=0 → 文字
        if text_chars < 80:  # 文字稀疏，判定为扫描页噪声
            ocr_candidates.append(i)

    if not ocr_candidates:
        return

    for i in ocr_candidates:
        try:
            pix = doc[i].get_pixmap(dpi=200)
            ocr_text = ocr_image(pix.tobytes("png"))
            if ocr_text.strip():
                pages_text[i] = ocr_text.strip()
                logger.info("OCR 成功 — 第 %d 页 (%d 字符)", i + 1, len(ocr_text))
            else:
                logger.warning("OCR 返回空 — 第 %d 页", i + 1)
        except Exception as e:
            logger.warning("OCR 失败 — 第 %d 页: %s", i + 1, e)
