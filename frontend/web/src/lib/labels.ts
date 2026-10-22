import type { DealCycle, DealType, PlatformCategory } from "./types";

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

export const CATEGORY_LABELS: Record<PlatformCategory, string> = {
  llm_api_cn: "国内大模型 API",
  llm_api_global: "海外大模型 API",
  coding_tool: "AI 编程工具",
  media_tool: "图像视频",
  cloud: "云服务",
};

export const CATEGORY_ORDER: PlatformCategory[] = [
  "llm_api_cn",
  "llm_api_global",
  "coding_tool",
  "media_tool",
  "cloud",
];
