from datetime import datetime

from langchain_core.tools import tool


@tool
def current_time() -> str:
    """获取当前日期和时间。不需要任何参数，返回当前年月日、时分秒和星期几。"""
    return datetime.now().strftime("%Y年%m月%d日 %H:%M:%S %A")
