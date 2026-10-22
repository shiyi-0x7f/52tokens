import type { Currency } from "./types";

const SYMBOL: Record<Currency, string> = { CNY: "¥", USD: "$" };

/** 十进制字符串 → 展示价格；去掉多余的 0，但至少保留两位小数 */
export function formatPrice(value: string | null, currency: Currency): string {
  if (value === null) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const digits = Math.max(2, Math.min(4, (value.split(".")[1] ?? "").replace(/0+$/, "").length));
  return `${SYMBOL[currency]}${n.toFixed(digits)}`;
}

/** 模型最低输出价：有人民币价优先显示人民币，否则显示美元（不做汇率换算） */
export function formatMinOutput(m: {
  min_output_price_cny: string | null;
  min_output_price_usd: string | null;
}): string {
  if (m.min_output_price_cny !== null) return formatPrice(m.min_output_price_cny, "CNY");
  return formatPrice(m.min_output_price_usd, "USD");
}

/** 相对时间：「12 分钟前」「3 天前」，超过 30 天显示日期 */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const diffSec = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  if (diffSec < 60) return "刚刚";
  const minutes = Math.floor(diffSec / 60);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days <= 30) return `${days} 天前`;
  return formatDate(iso);
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
}

export function formatContext(tokens: number | null): string {
  if (tokens === null) return "—";
  return tokens >= 1000 ? `${Math.round(tokens / 1000)}K` : String(tokens);
}
