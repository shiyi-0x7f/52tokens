import type { DealCycle, DealStatus, DealType, ShopCollectorKind } from "./types";

/** 店铺系统类型（决定采集方式） */
export const SHOP_KIND_LABELS: Record<ShopCollectorKind, string> = {
  kami: "Kami",
  dujiao: "独角数卡",
  shopApi: "ShopApi（多商户，如链动小铺）",
  shopGoodsApi: "ShopGoodsApi（多商户，如 16688）",
  xiaoheiwan: "小黑万",
  opensoraHtml: "OpenSora 页面",
  makerichHtml: "Makerich 页面",
  beibeiHtml: "贝贝页面",
  ikunloveApi: "IkunLove 接口",
  getgptApi: "GetGPT 接口",
  publicProductsApi: "公开商品接口",
  shopUserProductsApi: "Shop User 接口",
  unicornHtml: "Unicorn 页面",
  mooncakeCatalog: "Mooncake 目录",
  blackcatWholesale: "BlackCat 批发",
  genericHtml: "通用页面解析",
};

export const DEAL_TYPE_LABELS: Record<DealType, string> = {
  checkin_points: "签到",
  signup_credit: "注册送",
  free_quota: "免费额度",
  invite_reward: "邀请",
  discount: "折扣",
  student: "学生",
  trial: "试用",
  event: "活动",
};

export const CYCLE_LABELS: Record<DealCycle, string> = {
  once: "一次性",
  daily: "每日",
  monthly: "每月",
  ongoing: "长期",
};

export const DEAL_STATUS: Record<DealStatus, { label: string; color: string }> = {
  pending: { label: "待审核", color: "gold" },
  active: { label: "已发布", color: "green" },
  expired: { label: "已结束", color: "default" },
  rejected: { label: "已驳回", color: "red" },
};
