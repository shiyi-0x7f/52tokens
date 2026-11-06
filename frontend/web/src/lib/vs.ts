/**
 * 精选对比页 /models/{a}-vs-{b}：网址拼装，以及按两个模型的真实数据生成的要点和 FAQ。
 * 文案只陈述数据，不做主观推荐；币种不同不做汇率换算。
 */
import { lowest, type PriceField } from "./compare";
import type { FaqItem } from "./free";
import { formatContext, formatPrice } from "./format";
import type { ModelDetail } from "./types";

export function vsPath(a: string, b: string): string {
  return `/models/${a}-vs-${b}`;
}

function priceSentence(a: ModelDetail, b: ModelDetail, field: PriceField, label: string) {
  const pa = lowest(a, field);
  const pb = lowest(b, field);
  if (!pa || !pb) {
    const known = pa ? { m: a, p: pa } : pb ? { m: b, p: pb } : null;
    return known
      ? `只有 ${known.m.name} 有付费${label}数据：最低 ${formatPrice(String(known.p.value), known.p.currency)} / 百万 tokens。`
      : null;
  }
  const ta = formatPrice(String(pa.value), pa.currency);
  const tb = formatPrice(String(pb.value), pb.currency);
  if (pa.currency !== pb.currency) {
    return `最低${label}：${a.name} ${ta}，${b.name} ${tb}（币种不同，未换算）。`;
  }
  if (pa.value === pb.value) return `两者最低${label}相同，都是 ${ta} / 百万 tokens。`;
  const [cheap, dear, tc, td, vc, vd] =
    pa.value < pb.value ? [a, b, ta, tb, pa.value, pb.value] : [b, a, tb, ta, pb.value, pa.value];
  const saving = Math.round((1 - vc / vd) * 100);
  return `${cheap.name} 的${label}更低：最低 ${tc}，${dear.name} 最低 ${td}，便宜约 ${saving}%。`;
}

function contextSentence(a: ModelDetail, b: ModelDetail): string | null {
  const ca = a.context_window;
  const cb = b.context_window;
  if (ca === null || cb === null) return null;
  if (ca === cb) return `两者上下文窗口相同，都是 ${formatContext(ca)}。`;
  const [long, short] = ca > cb ? [a, b] : [b, a];
  return `${long.name} 的上下文更长：${formatContext(long.context_window)}，${short.name} 为 ${formatContext(short.context_window)}。`;
}

function freeSentence(a: ModelDetail, b: ModelDetail): string {
  const free = [a, b].filter((m) => m.prices.some((p) => p.is_free));
  if (free.length === 2) return `${a.name} 和 ${b.name} 都有免费可用的渠道（通常有频率限制）。`;
  if (free.length === 1) return `只有 ${free[0]?.name} 有免费可用的渠道（通常有频率限制）。`;
  return `${a.name} 和 ${b.name} 目前都没有收录到免费渠道。`;
}

export interface VsSummary {
  /** 页面顶部的要点，每条一句 */
  highlights: string[];
  faq: FaqItem[];
}

export function buildVsSummary(a: ModelDetail, b: ModelDetail): VsSummary {
  const output = priceSentence(a, b, "output_price", "输出价");
  const input = priceSentence(a, b, "input_price", "输入价");
  const context = contextSentence(a, b);
  const free = freeSentence(a, b);

  const faq: FaqItem[] = [];
  const priceAnswer = [output, input].filter((s): s is string => s !== null).join("");
  if (priceAnswer) faq.push({ q: `${a.name} 和 ${b.name} 哪个 API 更便宜？`, a: priceAnswer });
  if (context) faq.push({ q: `${a.name} 和 ${b.name} 哪个上下文更长？`, a: context });
  faq.push({ q: `${a.name} 和 ${b.name} 有免费的 API 吗？`, a: free });

  return {
    highlights: [output, input, context, free].filter((s): s is string => s !== null),
    faq,
  };
}
