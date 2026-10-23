import type { DealCycle, DealStatus, DealType } from "./types";

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
