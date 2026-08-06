import re
import math
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator-server")

# 允许的字符
_ALLOWED = re.compile(r"^[\d\s+\-*/\.()\%,_a-z]+$")


@mcp.tool()
def calculate(expression: str) -> str:
    """安全的数学表达式求值。支持 + - * / ** // % 及 math 函数。

    Args:
        expression: 数学表达式，如 "2 + 3 * 4"、"sqrt(16)+5"
    """

    cleaned = expression.strip().lower()
    if not _ALLOWED.match(cleaned):
        return "错误：表达式包含不允许的字符。"
    try:
        return str(eval(cleaned, {"__builtins__": {}}, {"math": math}))
    except Exception as e:
        return f"计算错误: {e}"


if __name__ == "__main__":
    mcp.settings.host = "127.0.0.1"
    mcp.settings.port = 8765
    mcp.run(transport="sse")
