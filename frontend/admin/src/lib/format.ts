import dayjs from "dayjs";
import "dayjs/locale/zh-cn";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

export function fromNow(iso: string | null): string {
  return iso ? dayjs(iso).fromNow() : "—";
}

export function formatDateTime(iso: string | null): string {
  return iso ? dayjs(iso).format("YYYY-MM-DD HH:mm") : "—";
}

export function formatPrice(value: string | null, currency: "CNY" | "USD"): string {
  if (value === null) return "—";
  const n = Number(value);
  return `${currency === "CNY" ? "¥" : "$"}${Number.isInteger(n * 100) ? n.toFixed(2) : String(n)}`;
}
