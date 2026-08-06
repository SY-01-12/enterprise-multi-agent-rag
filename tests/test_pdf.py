"""PDF Loader 测试 — 文本 PDF 解析 + 扫描件 OCR"""

from unittest.mock import patch, MagicMock

import fitz
from langchain_core.messages import AIMessage

from app.rag.loader.pdf import load_pdf, _ocr_blank_pages


# ══════════════════════════════════════════════════════
# 1. 正常文本 PDF 测试
# ══════════════════════════════════════════════════════

class TestPdfLoad:
    """测试 load_pdf 基本功能。"""

    def test_load_text_pdf(self):
        """文本 PDF 正常加载，返回 Document 列表。"""
        docs = load_pdf("tests/fixtures/test_text.pdf")
        assert len(docs) > 0
        for doc in docs:
            assert doc.page_content.strip()
            assert "source" in doc.metadata
            assert "page" in doc.metadata

    def test_load_text_pdf_has_content(self):
        """文本 PDF 能正确提取文字。"""
        docs = load_pdf("tests/fixtures/test_text.pdf")
        full_text = "".join(d.page_content for d in docs)
        assert len(full_text) > 20


# ══════════════════════════════════════════════════════
# 2. 扫描件 OCR 测试
# ══════════════════════════════════════════════════════

class TestScannedPdfOCR:
    """测试扫描 PDF 的 OCR 识别。"""

    def test_ocr_blank_pages_called(self):
        """空白页应触发 OCR 调用。"""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="OCR 识别结果：这是合同第一页")

        doc = fitz.open("tests/fixtures/test_text.pdf")
        pages_text = [""] * len(doc)

        with patch(
            "app.utils.ocr.get_vision_llm", return_value=mock_llm
        ):
            _ocr_blank_pages(doc, pages_text)

        doc.close()
        assert all(t.strip() for t in pages_text)

    def test_ocr_skips_non_blank(self):
        """有文字的页面不调用 OCR。"""
        doc = fitz.open("tests/fixtures/test_text.pdf")
        page_count = len(doc)
        pages_text = ["已有文字内容"] * page_count

        with patch("app.utils.ocr.get_vision_llm") as mock_get_llm:
            _ocr_blank_pages(doc, pages_text)
            mock_get_llm.assert_not_called()

        doc.close()
        assert pages_text == ["已有文字内容"] * page_count

    def test_ocr_handles_failure_gracefully(self):
        """OCR 失败时保留原空页，不抛异常。"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API 调用失败")

        doc = fitz.open("tests/fixtures/test_text.pdf")
        pages_text = [""]

        with patch(
            "app.utils.ocr.get_vision_llm", return_value=mock_llm
        ):
            _ocr_blank_pages(doc, pages_text)

        doc.close()
        assert pages_text[0] == ""

    def test_load_pdf_with_ocr(self):
        """完整流程：load_pdf 对空白页执行 OCR。"""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="扫描件识别文字")

        with patch(
            "app.utils.ocr.get_vision_llm", return_value=mock_llm
        ):
            docs = load_pdf("tests/fixtures/test_text.pdf")

        assert len(docs) > 0

    def test_scanned_pdf_ocr_triggered(self):
        """混合 PDF（含空白页）：空白页触发 OCR，文字页保持不变。"""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content="甲方应按照合同约定向乙方支付货款。\n乙方应确保产品质量符合国家标准。"
        )

        with patch(
            "app.utils.ocr.get_vision_llm", return_value=mock_llm
        ):
            docs = load_pdf("tests/fixtures/test_scanned.pdf")

        assert len(docs) == 3

        page1_doc = [d for d in docs if d.metadata["page"] == 1]
        assert len(page1_doc) == 1
        assert "甲方" in page1_doc[0].page_content

        non_ocr_docs = [d for d in docs if d.metadata["page"] != 1]
        for d in non_ocr_docs:
            assert "甲方" not in d.page_content
