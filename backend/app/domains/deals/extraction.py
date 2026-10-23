"""LLM 抽取：官方页面正文 → 结构化活动。LLM 只负责抽字段和给置信度，发布必须过人工审核。"""

import json
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.domains.deals.models import DealCycle, DealType

SYSTEM_PROMPT = f"""你是 AI 平台优惠活动信息抽取器。
用户给出某平台一个官方页面的正文，以及该平台已收录的活动。
从正文中找出面向普通用户、当前仍有效的优惠活动，只输出 JSON 对象：{{"deals": [...]}}。

每条活动的字段：
- title：简洁的活动标题，不超过 40 字
- deal_type：{" / ".join(t.value for t in DealType)} 之一
  （checkin_points 签到领积分，signup_credit 注册赠送，free_quota 长期免费额度，
  invite_reward 邀请奖励，discount 折扣或优惠码，student 学生或教育优惠，trial 试用，
  event 抽奖、比赛等其他活动）
- reward_text：奖励内容，带数值和单位，如「+200 积分/天」「100 万 tokens」，不超过 30 字
- cycle：{" / ".join(c.value for c in DealCycle)} 之一（一次性 / 每日 / 每月 / 长期）
- requirements：参与门槛列表，如「需实名」「需绑定信用卡」，每项不超过 15 字，没有就给空列表
- ends_at：正文写明的截止日期，格式 YYYY-MM-DD，没写就是 null，不要猜
- description：一两句话说明怎么参与，不超过 150 字
- in_app_only：只能在 App 或客户端内参与时为 true
- matches_existing：如果就是已收录活动中的某一条（同一项福利，即使措辞不同），填它的 slug，否则 null
- confidence：0 到 1，表示这条信息在正文中有多明确、多确定是当前有效的活动
- evidence：支撑这条活动的正文原句，不超过 120 字

规则：
- 只依据正文，不要用自己的知识补充或推测数字；正文没写的数字不要编
- 付费套餐的常规价格、已明确结束的活动、只面向企业的商务合作不算活动
- 没有活动时输出 {{"deals": []}}
"""

MIN_CONFIDENCE = 0.3  # 低于这个值视为噪声，不进审核队列
AUTO_CONFIRM_CONFIDENCE = 0.85  # 匹配到已发布活动且不低于这个值时，自动刷新核实时间


class ExtractedDeal(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    deal_type: DealType
    reward_text: str = Field(min_length=1, max_length=100)
    cycle: DealCycle = DealCycle.ONCE
    requirements: list[str] = Field(default_factory=list)
    ends_at: date | None = None
    description: str = Field(default="", max_length=2000)
    in_app_only: bool = False
    matches_existing: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: str = ""

    @field_validator("requirements")
    @classmethod
    def _clean_requirements(cls, value: list[str]) -> list[str]:
        return [v.strip()[:40] for v in value if v.strip()][:8]

    @field_validator("evidence")
    @classmethod
    def _clip_evidence(cls, value: str) -> str:
        return value.strip()[:300]


class Extraction(BaseModel):
    deals: list[ExtractedDeal] = Field(default_factory=list)


class ExistingDeal(BaseModel):
    slug: str
    title: str
    reward_text: str


def build_user_prompt(
    *, platform_name: str, url: str, text: str, existing: list[ExistingDeal]
) -> str:
    known = json.dumps([e.model_dump() for e in existing], ensure_ascii=False)
    return (
        f"平台：{platform_name}\n页面：{url}\n已收录的活动：{known}\n\n页面正文：\n<<<\n{text}\n>>>"
    )
