"""官网链接定位：用浏览器的文本片段（#:~:text=）让官方页面打开后直接滚到活动原文并高亮。

Chrome / Edge / Safari 支持；不支持的浏览器忽略片段，正常打开页面。
"""

import re
from urllib.parse import quote

# 原文较长时只用开头和结尾各一段（textStart,textEnd），匹配更稳
_SHORT_QUOTE = 40
_EDGE = 16
_SPACES = re.compile(r"\s+")


def normalize_space(text: str) -> str:
    return _SPACES.sub(" ", text).strip()


def quote_in_text(quote_text: str, page_text: str) -> bool:
    """原文是否逐字出现在页面正文里。比较时去掉全部空白：中文段落跨行提取时会多出换行。"""
    needle = _SPACES.sub("", quote_text)
    return bool(needle) and needle in _SPACES.sub("", page_text)


def _encode(part: str) -> str:
    # 「-」「,」「&」在文本片段语法里有特殊含义，必须编码
    return quote(part, safe="").replace("-", "%2D")


def locate_url(source_url: str, quote_text: str) -> str:
    """给官网链接加上定位原文的文本片段；没有原文或链接已带 # 时原样返回。"""
    text = normalize_space(quote_text)
    if not text or "#" in source_url:
        return source_url
    if len(text) <= _SHORT_QUOTE:
        directive = _encode(text)
    else:
        directive = f"{_encode(text[:_EDGE].strip())},{_encode(text[-_EDGE:].strip())}"
    return f"{source_url}#:~:text={directive}"
