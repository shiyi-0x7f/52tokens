/**
 * 登录失败原因：页面只用固定的原因代码传递（URL 参数），不把后端文案拼进 URL，
 * 避免被人构造带任意文字的「钓鱼」链接。
 */

export const REASON_MESSAGES = {
  cancelled: "你取消了授权。",
  expired: "登录请求已过期，请重新登录。",
  disabled: "这个账号已被禁用，如有疑问请联系我们。",
  conflict: "这个邮箱已经关联了另一个账号。",
  turnstile: "人机验证没有通过，请重试。",
  email_invalid: "邮箱地址无效，请检查后重试。",
  code_invalid: "验证码错误或已过期。",
  rate_limited: "操作太频繁，请稍后再试。",
  send_failed: "验证码邮件暂时发不出去，请稍后再试，或先用 Google / 微信登录。",
  unavailable: "登录服务暂时不可用，请稍后再试。",
  failed: "登录没有成功，请稍后再试。",
} as const;

export type Reason = keyof typeof REASON_MESSAGES;

export function isReason(value: string | null): value is Reason {
  return value !== null && Object.hasOwn(REASON_MESSAGES, value);
}

/** 后端业务码 / HTTP 状态 → 原因代码（业务码见 shared/error-codes.json） */
export function reasonFor(status: number, code: number): Reason {
  if (code === 40002) return "turnstile";
  if (code === 40003) return "expired";
  if (code === 40004) return "code_invalid";
  if (code === 50201) return "send_failed";
  if (status === 422 || code === 40000) return "email_invalid";
  if (status === 429) return "rate_limited";
  if (status === 403) return "disabled";
  if (status === 409) return "conflict";
  if (status === 502 || status === 503) return "unavailable";
  return "failed";
}
