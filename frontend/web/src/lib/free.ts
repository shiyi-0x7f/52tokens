/** /free/{model}：把一个模型的免费渠道、相关免费额度活动和最便宜的付费价整理成页面数据 */
import { formatPrice } from "./format";
import type { Currency, Deal, DealType, ModelDetail, Price } from "./types";

/** 能拿来「白嫖」这个模型的活动类型 */
export const FREE_DEAL_TYPES: DealType[] = ["free_quota", "signup_credit", "trial"];

const CHEAPEST_PAID_COUNT = 3;

export interface FaqItem {
  q: string;
  a: string;
}

export interface FreeGuide {
  freePrices: Price[];
  /** 提供这个模型的平台上进行中的免费额度 / 注册赠送 / 试用 */
  deals: Deal[];
  cheapestPaid: Price[];
  /** 既没有免费渠道也没有相关活动时不让搜索引擎收录（内容太薄） */
  indexable: boolean;
  faq: FaqItem[];
}

function paidOutput(p: Price): number | null {
  if (p.is_free || p.output_price === null) return null;
  const value = Number(p.output_price);
  return value > 0 ? value : null;
}

/** 币种之间不换算：有人民币价就只比人民币，否则比美元 */
function cheapest(prices: Price[]): Price[] {
  const paid = prices.filter((p) => paidOutput(p) !== null);
  const currency: Currency = paid.some((p) => p.currency === "CNY") ? "CNY" : "USD";
  return paid
    .filter((p) => p.currency === currency)
    .sort((a, b) => (paidOutput(a) ?? 0) - (paidOutput(b) ?? 0))
    .slice(0, CHEAPEST_PAID_COUNT);
}

export function buildFreeGuide(model: ModelDetail, candidates: Deal[]): FreeGuide {
  const freePrices = model.prices.filter((p) => p.is_free);
  const platforms = new Set(model.prices.map((p) => p.platform.slug));
  const seen = new Set<string>();
  const deals = candidates.filter((d) => {
    if (d.is_expired || !FREE_DEAL_TYPES.includes(d.deal_type)) return false;
    if (!platforms.has(d.platform.slug) || seen.has(d.slug)) return false;
    seen.add(d.slug);
    return true;
  });
  const cheapestPaid = cheapest(model.prices);

  const freeAnswer =
    freePrices.length > 0
      ? `有。${freePrices.map((p) => p.platform.name).join("、")} 可以免费调用 ${model.name}` +
        `${freePrices.some((p) => p.free_note) ? "，通常有请求频率或用量上限" : ""}。`
      : deals.length > 0
        ? `目前没有长期免费的渠道，但 ${[...new Set(deals.map((d) => d.platform.name))].join("、")} ` +
          `有免费额度或新用户赠送，可以用来调用 ${model.name}。`
        : `目前没有找到 ${model.name} 的免费渠道或免费额度，有新活动核实后会更新在这里。`;
  const faq: FaqItem[] = [{ q: `${model.name} 有免费的 API 吗？`, a: freeAnswer }];
  const top = cheapestPaid[0];
  if (top) {
    faq.push({
      q: `${model.name} API 最便宜多少钱？`,
      a:
        `付费渠道里 ${top.platform.name} 最便宜，输出 ${formatPrice(top.output_price, top.currency)}` +
        ` / 百万 tokens，输入 ${formatPrice(top.input_price, top.currency)} / 百万 tokens。`,
    });
  }

  return {
    freePrices,
    deals,
    cheapestPaid,
    indexable: freePrices.length > 0 || deals.length > 0,
    faq,
  };
}
