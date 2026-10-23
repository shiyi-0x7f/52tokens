/** 分享图（Open Graph）的卡片内容：只放当前页的单个实体，见 data-protection.md */
import { formatPrice } from "../format";
import { CYCLE_LABELS, DEAL_TYPE_LABELS } from "../labels";
import type { Currency, Deal, DealType, ModelDetail, Platform } from "../types";

export interface OgCard {
  /** 标题上方的小字，如「阿里云百炼 · 注册送」 */
  eyebrow: string;
  title: string;
  /** 大号红字，如奖励或最低价 */
  highlight?: string | undefined;
  /** 底部说明，如「每日 · 需在客户端内完成」 */
  note?: string | undefined;
  tags: string[];
}

export const DEFAULT_CARD: OgCard = {
  eyebrow: "52tokens",
  title: "AI 羊毛热榜",
  highlight: "免费额度 · 签到积分 · 模型价格",
  note: "每条标注出处与最近确认时间",
  tags: [],
};

export function dealCard(deal: Deal): OgCard {
  const note = [
    CYCLE_LABELS[deal.cycle],
    deal.in_app_only ? "需在客户端内完成" : "",
    deal.is_expired ? "已结束" : "",
  ].filter(Boolean);
  return {
    eyebrow: `${deal.platform.name} · ${DEAL_TYPE_LABELS[deal.deal_type]}`,
    title: deal.title,
    highlight: deal.reward_text,
    note: note.join(" · "),
    tags: deal.requirements.slice(0, 3),
  };
}

export function modelCard(model: ModelDetail): OgCard {
  const paid = model.prices.filter(
    (p) => !p.is_free && p.output_price !== null && Number(p.output_price) > 0,
  );
  const currency: Currency = paid.some((p) => p.currency === "CNY") ? "CNY" : "USD";
  const lowest = paid
    .filter((p) => p.currency === currency)
    .map((p) => p.output_price as string)
    .sort((a, b) => Number(a) - Number(b))[0];
  const freeCount = model.prices.filter((p) => p.is_free).length;
  return {
    eyebrow: "模型 API 价格",
    title: model.name,
    highlight: lowest ? `输出 ${formatPrice(lowest, currency)} / 百万 tokens 起` : undefined,
    note: `${model.prices.length} 个平台比价`,
    tags: freeCount > 0 ? [`${freeCount} 个免费渠道`] : [],
  };
}

export function platformCard(platform: Platform, activeDeals: Deal[]): OgCard {
  const types = [...new Set(activeDeals.map((d) => d.deal_type))] as DealType[];
  return {
    eyebrow: "平台优惠活动",
    title: platform.name,
    highlight: activeDeals.length > 0 ? `${activeDeals.length} 个进行中的活动` : undefined,
    note: activeDeals[0] ? `${activeDeals[0].title}：${activeDeals[0].reward_text}` : undefined,
    tags: types.slice(0, 4).map((t) => DEAL_TYPE_LABELS[t]),
  };
}
