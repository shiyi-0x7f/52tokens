"""归类用的文本工具：标题规范化、关键词匹配、正则编译。

正则写法沿用 JS 语义：`\\b` `\\w` `\\d` 只认 ASCII（Python 默认按 Unicode，中文算单词字符、
全角数字算 \\d，会让「买puls会员」里的 \\bpuls\\b 匹配不上），统一由 rx() 转换。
"""

import re
from collections.abc import Iterable
from functools import cache

_ASCII_WORD = "A-Za-z0-9_"
_BOUNDARY = f"(?:(?<=[{_ASCII_WORD}])(?![{_ASCII_WORD}])|(?<![{_ASCII_WORD}])(?=[{_ASCII_WORD}]))"
_OUTSIDE = {
    "b": _BOUNDARY,
    "d": "[0-9]",
    "D": "[^0-9]",
    "w": f"[{_ASCII_WORD}]",
    "W": f"[^{_ASCII_WORD}]",
}
_INSIDE = {"d": "0-9", "w": _ASCII_WORD}


def _ascii_escapes(pattern: str) -> str:
    out: list[str] = []
    in_class = False
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\" and i + 1 < len(pattern):
            nxt = pattern[i + 1]
            table = _INSIDE if in_class else _OUTSIDE
            out.append(table.get(nxt, ch + nxt))
            i += 2
            continue
        if ch == "[" and not in_class:
            in_class = True
        elif ch == "]" and in_class:
            in_class = False
        out.append(ch)
        i += 1
    return "".join(out)


@cache
def rx(pattern: str, ignore_case: bool = False) -> re.Pattern[str]:
    return re.compile(_ascii_escapes(pattern), re.IGNORECASE if ignore_case else 0)


def test(pattern: str, value: str) -> bool:
    return rx(pattern).search(value) is not None


def matches(value: str, needles: Iterable[str]) -> bool:
    return any(n.lower() in value for n in needles)


def has_nearby_negation(value: str, signal_pattern: str) -> bool:
    """「非 / 不是 / 不含 / 无 / not」紧挨着信号词时，视为否定。"""
    scoped = rx(rf"(?:非|不是|不含)\s*(?:[^\s]{{1,8}}\s+)?{signal_pattern}", ignore_case=True)
    direct = rx(rf"(?:无\s*|not\s+){signal_pattern}", ignore_case=True)
    return scoped.search(value) is not None or direct.search(value) is not None


_REPLACEMENTS: list[tuple[str, str]] = [
    ("美國", "美国"),
    ("虛擬", "虚拟"),
    (r"[×✕✖✘]", "x"),
    ("[︎️]", ""),
    (r"[｜|/【】\[\]()（）,，:：\-_/–—]+", " "),
    ("gptplus", "gpt plus"),
    ("plus月卡", "plus 月卡"),
    ("普拉斯", "plus"),
    (r"\bpuls\b", "plus"),
    (r"\bpulus\b", "plus"),
    (r"\bgemin\b", "gemini"),
    (r"\bgtp\b", "gpt"),
    (r"\bcoedx\b", "codex"),
    (r"\bcluade\b", "claude"),
    (r"\bbusisness\b", "business"),
    (r"chat\s*gpt", "chatgpt"),
    (r"claude\s*code", "claude code"),
    ("supergrok", "super grok"),
    (r"\s+", " "),
]


def normalize_title(title: str) -> str:
    value = title.lower()
    for pattern, repl in _REPLACEMENTS:
        value = rx(pattern).sub(repl, value)
    return value.strip()
