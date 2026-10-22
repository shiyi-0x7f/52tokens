/**
 * 模型参数对比表：把若干模型的详情整理成「一行一项参数」的表格，
 * 标出每行最优的值，并标记各模型取值是否相同（用于「只看不同项」）。
 */
import { familyLabel } from "./families";
import { formatContext, formatPrice, formatRelative } from "./format";
import type { Currency, ModelDetail, Price } from "./types";

export interface CompareCell {
  text: string;
  best: boolean;
}

export interface CompareRow {
  label: string;
  group: "基本信息" | "最低价格（每百万 tokens）" | "各平台价格（输入 / 输出，每百万 tokens）";
  cells: CompareCell[];
  /** 各模型取值都相同 */
  same: boolean;
}

type PriceField = "input_price" | "output_price" | "cache_read_price";

/** 模型在某价格项上的最低付费价：有人民币价用人民币，否则美元 */
function lowest(
  model: ModelDetail,
  field: PriceField,
): { value: number; currency: Currency } | null {
  for (const currency of ["CNY", "USD"] as const) {
    const values = model.prices
      .filter((p) => p.currency === currency && p[field] !== null && Number(p[field]) > 0)
      .map((p) => Number(p[field]));
    if (values.length > 0) return { value: Math.min(...values), currency };
  }
  return null;
}

/** 数值越小越好的一行：只在同币种之间比较（不做汇率换算） */
function priceRow(models: ModelDetail[], field: PriceField, label: string): CompareRow {
  const values = models.map((m) => lowest(m, field));
  const currencies = values.filter((v) => v !== null).map((v) => v.currency);
  // 出现最多的币种参与比较；数量相同时优先人民币
  const majority: Currency =
    currencies.filter((c) => c === "CNY").length >= currencies.filter((c) => c === "USD").length
      ? "CNY"
      : "USD";
  const comparable = values.filter((v) => v?.currency === majority).map((v) => v?.value ?? 0);
  // 至少两个可比且取值有差异时才标出最优，全部相同不标
  const min =
    comparable.length > 1 && new Set(comparable).size > 1 ? Math.min(...comparable) : null;
  return finish(
    label,
    "最低价格（每百万 tokens）",
    values.map((v) => ({
      text: v ? formatPrice(String(v.value), v.currency) : "—",
      best: v !== null && min !== null && v.currency === majority && v.value === min,
    })),
  );
}

function finish(label: string, group: CompareRow["group"], cells: CompareCell[]): CompareRow {
  return { label, group, cells, same: cells.every((c) => c.text === cells[0]?.text) };
}

function maxRow(label: string, values: (number | null)[], render: (v: number | null) => string) {
  const present = values.filter((v): v is number => v !== null);
  const max = present.length > 1 ? Math.max(...present) : null;
  return finish(
    label,
    "基本信息",
    values.map((v) => ({
      text: render(v),
      best: v !== null && max !== null && v === max && present.some((p) => p !== max),
    })),
  );
}

function platformCell(price: Price | undefined): string {
  if (!price) return "—";
  if (price.is_free && price.output_price === null) return "免费";
  const text = `${formatPrice(price.input_price, price.currency)} / ${formatPrice(price.output_price, price.currency)}`;
  return price.is_free ? `${text}（另有免费版）` : text;
}

export function buildCompareRows(models: ModelDetail[], now: Date = new Date()): CompareRow[] {
  const rows: CompareRow[] = [
    finish(
      "系列",
      "基本信息",
      models.map((m) => ({ text: familyLabel(m.family), best: false })),
    ),
    maxRow(
      "上下文窗口",
      models.map((m) => m.context_window),
      (v) => formatContext(v),
    ),
    maxRow(
      "收录平台数",
      models.map((m) => m.prices.length),
      (v) => String(v ?? 0),
    ),
    finish(
      "免费渠道",
      "基本信息",
      models.map((m) => {
        const free = m.prices.some((p) => p.is_free);
        return {
          text: free ? "有" : "无",
          best: free && models.some((o) => !o.prices.some((p) => p.is_free)),
        };
      }),
    ),
    priceRow(models, "input_price", "最低输入价"),
    priceRow(models, "output_price", "最低输出价"),
    priceRow(models, "cache_read_price", "最低缓存命中价"),
  ];

  const platforms = new Map<string, string>();
  for (const m of models) for (const p of m.prices) platforms.set(p.platform.slug, p.platform.name);
  for (const [slug, name] of platforms) {
    rows.push(
      finish(
        name,
        "各平台价格（输入 / 输出，每百万 tokens）",
        models.map((m) => ({
          text: platformCell(m.prices.find((p) => p.platform.slug === slug)),
          best: false,
        })),
      ),
    );
  }

  rows.push(
    finish(
      "最近核实",
      "基本信息",
      models.map((m) => {
        const latest = m.prices
          .map((p) => p.confirmed_at)
          .sort()
          .at(-1);
        return { text: latest ? formatRelative(latest, now) : "—", best: false };
      }),
    ),
  );
  return rows;
}
