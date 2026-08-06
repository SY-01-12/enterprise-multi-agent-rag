

from __future__ import annotations

import base64
import logging

from langchain_core.messages import HumanMessage

from app.llm import get_vision_llm

logger = logging.getLogger(__name__)

_DEFAULT_OCR_PROMPT = "请提取这张图片中的全部文字，只输出提取到的文字内容，不要添加任何其他说明。"


def ocr_image(
    image_bytes: bytes,
    prompt: str | None = None,
    *,
    mime: str = "image/png",
) -> str:

    img_b64 = base64.b64encode(image_bytes).decode()
    llm = get_vision_llm()

    response = llm.invoke([
        HumanMessage(content=[
            {"type": "text", "text": prompt or _DEFAULT_OCR_PROMPT},
            {"type": "image_url", "image_url": {
                "url": f"data:{mime};base64,{img_b64}"
            }},
        ])
    ])
    return response.content if hasattr(response, "content") else str(response)
