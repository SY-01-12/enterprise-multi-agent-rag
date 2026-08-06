import json
import time
import threading
import urllib.error
import urllib.request

from langchain_core.tools import tool
from app.core.config import get_settings

BASE = "https://dashscope.aliyuncs.com/api/v1"

# 线程安全的存储，用于在工具执行和 SSE 事件处理之间传递图片 URL
# key: (thread_id, prompt_hash) → value: {"url": str, "prompt": str}
_last_image: dict[str, dict] = {}
_lock = threading.Lock()


def _call(api_key: str, path: str, data: dict | None = None, timeout: int = 30) -> dict:
    """通用 DashScope API 调用，返回解析后的 JSON。"""
    h = {"Authorization": f"Bearer {api_key}"}
    body = None
    if data is not None:
        h.update({"Content-Type": "application/json", "X-DashScope-Async": "enable"})
        body = json.dumps(data).encode()
    try:
        req = urllib.request.Request(f"{BASE}{path}", body, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:500]}") from e


@tool
def generate_image(prompt: str) -> str:
    """根据文字描述生成图片（DashScope wanx-v1）。"""
    api_key = get_settings().API_KEY
    if not api_key:
        return "未配置 API_KEY，无法生成图片。"

    try:
        task_id = _call(api_key, "/services/aigc/text2image/image-synthesis", {
            "model": "wanx-v1",
            "input": {"prompt": prompt},
            "parameters": {"size": "1024*1024", "n": 1},
        }).get("output", {}).get("task_id")
    except RuntimeError as e:
        return f"图片生成请求失败: {e}"
    if not task_id:
        return "图片生成失败：未获取到任务 ID"

    for _ in range(20):
        time.sleep(2)
        try:
            output = _call(api_key, f"/tasks/{task_id}", timeout=15).get("output", {})
        except Exception as e:
            return f"查询任务状态失败: {e}"
        if output.get("task_status") == "SUCCEEDED":
            img = (output.get("results") or [{}])[0].get("url")
            if img:
                # 将 URL 存入线程安全存储，供 SSE handler 读取
                with _lock:
                    _last_image["url"] = img
                    _last_image["prompt"] = prompt
                # 不在返回值中包含图片 URL，防止 LLM 在文本中重复输出
                return f"图片已生成！提示词: {prompt}\n请查看生成的图片。"
            return "任务完成但无法提取图片链接"
        if output.get("task_status") == "FAILED":
            return f"图片生成失败: {output.get('message', '未知错误')}"

    return f"图片生成任务已提交（task_id: {task_id}），但 40 秒内未完成，请稍后重试。"


def get_last_image() -> dict:
    """获取最近一次生成的图片信息（线程安全）。"""
    with _lock:
        return dict(_last_image)


def clear_last_image() -> None:
    """清除存储的图片信息。"""
    with _lock:
        _last_image.clear()
