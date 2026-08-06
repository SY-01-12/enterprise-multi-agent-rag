from langchain_core.language_models import BaseChatModel

from app.llm.bailian import get_llm as get_bailian_llm
from app.llm.ollama import get_ollama_llm
from app.llm.vision import get_vision_llm  # noqa: F401 — ocr.py 需要


def get_llm(model_name: str | None = None) -> BaseChatModel:
    """根据模型标识获取 LLM 实例。

    支持前缀：
    - bailian: → 百炼模型（DashScope 兼容 OpenAI 接口）
    - ollama:  → 本地 Ollama 模型
    - 无前缀   → 默认百炼模型
    """
    name = model_name or ""

    if name.startswith("ollama:"):
        return get_ollama_llm(name.replace("ollama:", "", 1))
    elif name.startswith("bailian:"):
        return get_bailian_llm(name.replace("bailian:", "", 1))
    else:
        return get_bailian_llm()
