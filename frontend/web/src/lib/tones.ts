/** 类型 → 色调：让不同类型一眼可辨。色值在 global.css 的 --color-tone-* 令牌里 */
import type { DealType } from "./types";

export type Tone =
  "amber" | "green" | "teal" | "violet" | "rose" | "blue" | "indigo" | "orange" | "sky" | "slate";

/** Tailwind 需要完整类名才能生成样式，不能拼接 */
export const TONE_CLASS: Record<Tone, string> = {
  amber: "bg-tone-amber-bg text-tone-amber",
  green: "bg-tone-green-bg text-tone-green",
  teal: "bg-tone-teal-bg text-tone-teal",
  violet: "bg-tone-violet-bg text-tone-violet",
  rose: "bg-tone-rose-bg text-tone-rose",
  blue: "bg-tone-blue-bg text-tone-blue",
  indigo: "bg-tone-indigo-bg text-tone-indigo",
  orange: "bg-tone-orange-bg text-tone-orange",
  sky: "bg-tone-sky-bg text-tone-sky",
  slate: "bg-tone-slate-bg text-tone-slate",
};

export const DEAL_TYPE_TONES: Record<DealType, Tone> = {
  checkin_points: "amber",
  signup_credit: "green",
  free_quota: "teal",
  invite_reward: "violet",
  discount: "rose",
  student: "blue",
  trial: "indigo",
  event: "slate",
};

/** 卡网对外展示的商品类型（标准商品的 product_type；接码、邮箱、虚拟卡等已不展示） */
const SHOP_TYPE_TONES: Record<string, Tone> = {
  "订阅/会员": "violet",
  成品账号: "blue",
  辅助服务: "slate",
  API额度: "teal",
  工具账号: "indigo",
  礼品卡: "amber",
};

export function shopTypeTone(productType: string): Tone {
  return SHOP_TYPE_TONES[productType] ?? "slate";
}
