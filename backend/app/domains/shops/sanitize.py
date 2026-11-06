"""对外展示的卡网文案去敏。只改展示，不改库里的原文（归类规则仍按原文识别）。

- 敏感说法换成中性措辞（如「接码」→「手机验证」），新增敏感词在 REPLACEMENTS 里加一行；
- 去掉网址和域名：页面上不出现任何店铺的网址，店铺用 shop_alias 生成的代号区分。
"""

import hashlib
import re

REPLACEMENTS: tuple[tuple[str, str], ...] = (("接码", "手机验证"),)

_PATTERN = re.compile("|".join(re.escape(src) for src, _ in REPLACEMENTS))
_MAP = dict(REPLACEMENTS)

# 网址（带协议或 www.）与常见后缀的裸域名，如 https://a.shop/x、www.b.com、faka.c.top
_URL = re.compile(r"(?:https?://|www\.)[^\s，,；;）)】\]]+", re.IGNORECASE)
# 用前后断言而不是 \b：中文也算单词字符，「官网abc.com」里 \b 找不到边界
_DOMAIN = re.compile(
    r"(?<![a-z0-9-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|cn|net|org|shop|store|top|xyz|vip|cc|io|me|pro|club|site|online|link|fun|icu|cfd"
    r"|wiki|info|biz|tech|cloud|dev|uk|co|app|live|work|ink|ltd|asia|tv|in)(?![a-z0-9-])",
    re.IGNORECASE,
)
_SPACES = re.compile(r"\s{2,}")
_DANGLING = re.compile(r"[（(【\[]\s*[）)】\]]")  # 去掉网址后留下的空括号


def public_text(text: str) -> str:
    text = _PATTERN.sub(lambda m: _MAP[m.group(0)], text)
    text = _DOMAIN.sub("", _URL.sub("", text))
    return _SPACES.sub(" ", _DANGLING.sub(" ", text)).strip()


def shop_alias(host: str) -> str:
    """店铺代号：同一店铺固定不变，便于区分多条报价，但看不出是哪个网站。"""
    digest = hashlib.sha1(host.lower().encode(), usedforsecurity=False).hexdigest()
    return f"店铺 {digest[:4].upper()}"
