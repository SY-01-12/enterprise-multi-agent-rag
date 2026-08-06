import re

#  页码正则
PAGE_RE = re.compile(
    r"^\s*(?:\d{1,4}(?:\s*/\s*\d{1,4})?|[-–—]+\s*\d{1,4}\s*[-–—]+"
    r"|[第]?\s*\d{1,4}\s*[页頁]|page\s*\d{1,4})\s*$",
    re.IGNORECASE | re.MULTILINE,
)

#  控制字符
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
ZERO_WIDTH_RE = re.compile(r"[​‌‍‎‏­]")

#  空白
MULTI_NL_RE = re.compile(r"\n{3,}")
TRAIL_SPACE_RE = re.compile(r"[ \t]+$", re.MULTILINE)

#  清洗单页文本：去控制字符 → 去页码 → 规范化空白
def clean_document_text(text: str) -> str:

    text = ZERO_WIDTH_RE.sub("", text.replace("�", ""))
    text = CTRL_RE.sub(" ", text)
    text = PAGE_RE.sub("", text)
    text = MULTI_NL_RE.sub("\n\n", TRAIL_SPACE_RE.sub("", text))
    return text.strip()

#  过滤空页与噪声页（无有效中文/英文内容）
def filter_noise_pages(pages: list[str]) -> list[str]:

    return [t for p in pages if not is_noise(t := clean_document_text(p))]

#  跨页去重：高频率出现的行（如页眉页脚）视为噪声删除
def dedup_repeated_lines(pages: list[str]) -> list[str]:

    if len(pages) < 3:
        return pages

    threshold = max(2, int(len(pages) * 0.4))
    freq: dict[str, int] = {}
    for page in pages:
        seen = {l.strip() for l in page.split("\n") if l.strip()}
        for line in seen:
            freq[line] = freq.get(line, 0) + 1

    repeated = {line for line, c in freq.items() if c >= threshold}
    return ["\n".join(l for l in page.split("\n") if l.strip() not in repeated) for page in pages]

# 判断是否为噪声：空白 / 有效字符过少
def is_noise(text: str) -> bool:

    content = re.sub(r"[\s\d\W_]+", "", text.strip())
    return len(content) < 5 or (len(content) < 15 and "\n" not in text)
