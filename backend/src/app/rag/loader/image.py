from __future__ import annotations

import logging
import os

from langchain_core.documents import Document

from app.utils.ocr import ocr_image

logger = logging.getLogger(__name__)


#   MIME 就是文件的"身份证类型"
MIME_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
}

_IMAGE_PROMPT = (
    "请详细描述这张图片中的所有内容。"
    "如果图片中有文字，请完整转录出来。"
    "如果图片中有表格、图表、流程图，请用文字描述其结构和数据。"
    "用中文回答。"
)

# 加载图片
def load_image(file_path: str) -> list[Document]:
    ext = os.path.splitext(file_path)[-1].lstrip(".").lower()
    mime = MIME_MAP.get(ext, "image/jpeg")

    with open(file_path, "rb") as f:
        img_bytes = f.read()

    try:
        description = ocr_image(img_bytes, prompt=_IMAGE_PROMPT, mime=mime)

        return [Document(
            page_content=description,
            metadata={"source": file_path},
        )]

    except Exception as e:
        logger.warning("VL 模型调用失败，回退为基础元数据 (file=%s): %s", file_path, e)
        return [Document(
            page_content=(
                f"[图片文件: {os.path.basename(file_path)}]\n"
                f"格式: {ext.upper()}\n"
                f"（VL 模型不可用，图片内容未能转为文本描述）"
            ),
            metadata={"source": file_path},
        )]
