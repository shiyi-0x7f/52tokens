/** 与后端 /api/admin 响应结构对应（见 dev_docs/api/README.md）。金额为十进制字符串。 */

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Me {
  id: number;
  nickname: string;
  avatar_url: string | null;
  is_admin: boolean;
}

export type PublishStatus = "draft" | "active" | "hidden";
export type PlatformCategory =
  "llm_api_cn" | "llm_api_global" | "coding_tool" | "media_tool" | "cloud";

export interface Platform {
  id: number;
  slug: string;
  name: string;
  category: PlatformCategory;
  status: PublishStatus;
}

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
export type DealStatus = "pending" | "active" | "expired" | "rejected";

export interface Deal {
  id: number;
  slug: string;
  platform: { id: number; slug: string; name: string };
  title: string;
  deal_type: DealType;
  reward_text: string;
  est_value_cny: string | null;
  requirements: string[];
  cycle: DealCycle;
  starts_at: string | null;
  ends_at: string | null;
  description: string;
  steps: string[];
  source_url: string;
  source_quote: string;
  aff_url: string | null;
  in_app_only: boolean;
  status: DealStatus;
  confirmed_at: string | null;
  reviewed_at: string | null;
  reject_reason: string;
  origin: DealOrigin;
  /** 采集时 LLM 给的置信度（0–1），人工录入为 null */
  extract_confidence: string | null;
  /** 采集时抽取依据的原文 */
  extract_note: string;
  /** 存活检查：最近一次回访官网的时间、发现的下线信号与连续次数 */
  liveness_checked_at: string | null;
  liveness_issue: string;
  liveness_fail_count: number;
  created_at: string;
  updated_at: string;
}

export type DealOrigin = "manual" | "collector";

export interface DealInput {
  platform_id: number;
  slug?: string | null;
  title: string;
  deal_type: DealType;
  reward_text: string;
  est_value_cny?: number | null;
  requirements: string[];
  cycle: DealCycle;
  starts_at?: string | null;
  ends_at?: string | null;
  description: string;
  steps: string[];
  source_url: string;
  source_quote: string;
  aff_url?: string | null;
  in_app_only: boolean;
}

export interface Source {
  id: number;
  platform: { id: number; slug: string; name: string };
  url: string;
  label: string;
  enabled: boolean;
  checked_at: string | null;
  /** 上次正文变化并完成抽取的时间 */
  changed_at: string | null;
  last_error: string;
  fail_count: number;
  created_at: string;
}

export interface SourceInput {
  platform_id: number;
  url: string;
  label: string;
  enabled: boolean;
}

export interface CheckReport {
  source_id: number;
  status: "failed" | "unchanged" | "extracted";
  created: number;
  reconfirmed: number;
  error: string;
}

export interface BatchStatus {
  running: { started_at: string; total: number; done: number } | null;
  last: {
    started_at: string;
    finished_at: string;
    checked: number;
    created: number;
    reconfirmed: number;
    failed: number;
  } | null;
}

export type ShopCollectorKind =
  | "kami"
  | "dujiao"
  | "shopApi"
  | "shopGoodsApi"
  | "xiaoheiwan"
  | "opensoraHtml"
  | "makerichHtml"
  | "beibeiHtml"
  | "ikunloveApi"
  | "getgptApi"
  | "publicProductsApi"
  | "shopUserProductsApi"
  | "unicornHtml"
  | "mooncakeCatalog"
  | "blackcatWholesale"
  | "genericHtml";

export interface ShopSource {
  id: number;
  host: string;
  /** 店铺地址；多商户平台（shopApi / shopGoodsApi）是具体商户的 /shop/<token> */
  entry_url: string;
  name: string;
  collector_kind: ShopCollectorKind;
  enabled: boolean;
  checked_at: string | null;
  success_at: string | null;
  last_error: string;
  fail_count: number;
  offer_count: number;
}

export interface ShopSourceInput {
  entry_url: string;
  collector_kind: ShopCollectorKind;
  name: string;
  enabled: boolean;
}

export interface ShopSyncReport {
  source_id: number;
  status: "synced" | "failed";
  offers: number;
  created: number;
  gone: number;
  error: string;
}

export type Currency = "CNY" | "USD";

export interface Price {
  id: number;
  platform: Platform;
  model: { id: number; slug: string; name: string; family: string };
  currency: Currency;
  input_price: string | null;
  output_price: string | null;
  cache_read_price: string | null;
  is_free: boolean;
  free_note: string;
  source_url: string;
  confirmed_at: string | null;
  status: PublishStatus;
  updated_at: string;
}

export interface PriceInput {
  platform_id: number;
  model_slug: string;
  model_name?: string | null;
  family?: string | null;
  context_window?: number | null;
  currency: Currency;
  input_price?: number | null;
  output_price?: number | null;
  cache_read_price?: number | null;
  is_free: boolean;
  free_note: string;
  source_url: string;
}
