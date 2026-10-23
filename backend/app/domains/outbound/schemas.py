"""出站跳转对外数据结构（只给公开站服务端用）。"""

from pydantic import BaseModel, Field


class ClickIn(BaseModel):
    referer_path: str = Field(default="", max_length=200)


class RedirectOut(BaseModel):
    url: str
    # 为 True 时是推广链接：公开站跳转时带 rel="sponsored"，入口处必须已标「推广」
    is_promoted: bool
