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
  source_url: string;
  /** 官网原文摘录（逐字出现在官方页面上），没有时为空串 */
  source_quote: string;
  /** 带 #:~:text= 文本片段的官网链接，打开后滚到原文；没有原文时同 source_url */
  source_locate_url: string;
  in_app_only: boolean;
  confirmed_at: string;
  is_expired: boolean;
}
