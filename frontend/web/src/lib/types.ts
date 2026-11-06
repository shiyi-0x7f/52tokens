/** 与后端 /internal/v1 响应结构对应（见 dev_docs/api/README.md）。金额为十进制字符串。 */

export type PlatformCategory =
  "llm_api_cn" | "llm_api_global" | "coding_tool" | "media_tool" | "cloud";

export type Currency = "CNY" | "USD";

export type DealType =
  | "checkin_points"
  | "signup_credit"
  | "free_quota"
  | "invite_reward"
  | "discount"
  | "student"
  | "trial"
  | "event";

export type DealCycle = "once" | "daily" | "monthly" | "ongoing";

export interface PlatformRef {
  slug: string;
  name: string;
}

export interface Platform extends PlatformRef {
  category: PlatformCategory;
  website_url: string;
  description: string;
}

export interface Price {
  platform: PlatformRef;
  currency: Currency;
  input_price: string | null;
  output_price: string | null;
  cache_read_price: string | null;
  is_free: boolean;
  free_note: string;
  source_url: string;
  confirmed_at: string;
}

export interface ModelSummary {
  slug: string;
  name: string;
  family: string;
  context_window: number | null;
  min_output_price_cny: string | null;
  min_output_price_usd: string | null;
  has_free: boolean;
  price_count: number;
}

export interface ModelDetail {
  slug: string;
  name: string;
  family: string;
  context_window: number | null;
  description: string;
  prices: Price[];
}

export interface ModelRef {
  slug: string;
  name: string;
  family: string;
}

/** 后台精选的模型对比；顺序即规范网址 /models/{a}-vs-{b} 的顺序 */
export interface ModelComparison {
  model_a: ModelRef;
  model_b: ModelRef;
  intro: string;
  updated_at: string;
}

/** 官方订阅地区价（各国 App Store）；人民币价按快照当天汇率折算 */
export interface RegionPrice {
  country_code: string;
  country_label: string;
  currency: string;
  /** 当地货币原文，如 "$19.99" */
  price_text: string;
  cny_price: string | null;
  /** 相对美区人民币价的百分比（美区 = 100） */
  vs_us_percent: number | null;
  source_url: string;
  fx_date: string | null;
}

export interface OfficialPlanSummary {
  app_slug: string;
  app_name: string;
  provider: string;
  plan_slug: string;
  plan_name: string;
  billing_period: string;
  us: RegionPrice | null;
  cheapest: RegionPrice | null;
  region_count: number;
  fetched_at: string | null;
}

export interface OfficialPlanDetail extends OfficialPlanSummary {
  prices: RegionPrice[];
  missing_regions: string[];
}

/** 卡网比价：外层只有价格和有货店铺数，不出现商家名 */
export interface ShopProductSummary {
  slug: string;
  name: string;
  platform: string;
  product_type: string;
  spec: string;
  /** 有货最低价（人民币）：只算近 48 小时采集到且有货的报价 */
  min_price: string | null;
  in_stock_shops: number;
  offer_count: number;
}

export interface ShopOffer {
  /** 店铺原标题 */
  title: string;
  price: string;
  stock: number | null;
  in_stock: boolean;
  /** 跳转标识：链接到 /go/offer/{token}（页内弹窗提示后再去店铺），店铺链接不下发 */
  token: string;
  /** 店铺域名 */
  shop: string;
  tags: string[];
  /** 「拼车」「价格待核实」：照常展示，但不参与有货最低价 */
  flags: string[];
  last_seen_at: string;
  /** 近 48 小时采集到过；否则可能已失效 */
  is_fresh: boolean;
}

export interface ShopProductDetail extends ShopProductSummary {
  summary: string;
  offers: ShopOffer[];
}

export interface Deal {
  slug: string;
  title: string;
  deal_type: DealType;
  platform: PlatformRef;
  reward_text: string;
  est_value_cny: string | null;
  requirements: string[];
  cycle: DealCycle;
  starts_at: string | null;
  ends_at: string | null;
  description: string;
  /** 参与步骤，按顺序 */
  steps: string[];
  is_promoted: boolean;
  /** 「去参与」落地网站的域名，点击时弹窗提示用 */
  link_host: string;
  source_url: string;
  /** 官网原文摘录（逐字出现在官方页面上），没有时为空串 */
  source_quote: string;
  /** 带 #:~:text= 文本片段的官网链接，打开后滚到原文；没有原文时同 source_url */
  source_locate_url: string;
  in_app_only: boolean;
  confirmed_at: string;
  is_expired: boolean;
}
