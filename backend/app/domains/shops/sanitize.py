"""对外展示的卡网文案去敏：店铺标题里常带「接码」等容易违规的说法，展示时换成中性措辞。

只改展示，不改库里的原文（归类规则仍按原文识别）。新增敏感词在 REPLACEMENTS 里加一行。
"""

import re

REPLACEMENTS: tuple[tuple[str, str], ...] = (("接码", "手机验证"),)

_PATTERN = re.compile("|".join(re.escape(src) for src, _ in REPLACEMENTS))
_MAP = dict(REPLACEMENTS)


def public_text(text: str) -> str:
    return _PATTERN.sub(lambda m: _MAP[m.group(0)], text)
