"""测试 Ollama LLM 连接。

前提条件：
1. Ollama 服务已启动（默认 http://localhost:11434）
2. 已拉取对应模型：ollama pull qwen3.5:4b

用法：
    python app/test_llm.py
"""

from app.langchain_app.llm.ollama import get_llm


def main():
    print("=" * 50)
    print("Ollama LLM 连接测试")
    print("=" * 50)

    # 1. 获取 LLM 实例
    print("\n[1] 获取 LLM 实例...")
    llm = get_llm()
    print(f"    模型: {llm.model}")
    print(f"    地址: {llm.base_url}")
    print("    ✓ 实例创建成功")

    # 2. 发送测试消息
    print("\n[2] 发送测试消息: '你好，介绍一下自己'")
    print("    等待回复...")
    response = llm.invoke("你好，介绍一下自己")
    print(f"    回复: {response.content}")

    print("\n" + "=" * 50)
    print("测试完成 ✓")
    print("=" * 50)


if __name__ == "__main__":
    main()
