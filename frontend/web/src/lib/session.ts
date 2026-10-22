import type { AstroCookies } from "astro";

import { ApiError, internalSend } from "./api";
import { type Reason, reasonFor } from "./auth-reasons";
import { logger } from "./logger";

export const SESSION_COOKIE = "t52_session";
/** 登录流程中的短期 Cookie：OAuth state（防登录 CSRF）、待验证的邮箱 */
export const GOOGLE_STATE_COOKIE = "t52_google_state";
export const WECHAT_STATE_COOKIE = "t52_wx_state";
export const PENDING_EMAIL_COOKIE = "t52_email";
const FLOW_COOKIE_MAX_AGE = 600;

export interface SessionUser {
  id: number;
  nickname: string;
  avatar_url: string | null;
  is_admin: boolean;
}

export interface SessionData {
  session_token: string;
  expires_in: number;
  next: string;
  user: SessionUser;
}

const baseCookie = {
  httpOnly: true,
  sameSite: "lax",
  // 生产在 HTTPS 反代之后，Node 看到的协议是 http，所以按环境而不是按请求协议判断
  secure: import.meta.env.PROD,
  path: "/",
} as const;

export function setSessionCookie(cookies: AstroCookies, token: string, maxAgeSeconds: number) {
  cookies.set(SESSION_COOKIE, token, { ...baseCookie, maxAge: maxAgeSeconds });
}

export function clearSessionCookie(cookies: AstroCookies) {
  cookies.delete(SESSION_COOKIE, { path: "/" });
}

export function setFlowCookie(cookies: AstroCookies, name: string, value: string) {
  cookies.set(name, value, { ...baseCookie, maxAge: FLOW_COOKIE_MAX_AGE });
}

/** 取出并删除流程 Cookie（只能用一次） */
export function takeFlowCookie(cookies: AstroCookies, name: string): string | undefined {
  const value = cookies.get(name)?.value;
  cookies.delete(name, { path: "/" });
  return value;
}

/** 按 Cookie 查当前用户；会话失效时顺手清掉 Cookie，后端不可用时按未登录处理 */
export async function resolveUser(cookies: AstroCookies): Promise<SessionUser | null> {
  const token = cookies.get(SESSION_COOKIE)?.value;
  if (!token) return null;
  try {
    return await internalSend<SessionUser>("GET", "/auth/session", { sessionToken: token });
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      clearSessionCookie(cookies);
    } else {
      logger.error({ err }, "session lookup failed");
    }
    return null;
  }
}

export function reasonFromError(err: unknown): Reason {
  if (err instanceof ApiError) return reasonFor(err.status, err.code);
  logger.error({ err }, "login flow failed");
  return "failed";
}

/** 登录失败统一回到登录页，带固定的原因代码 */
export function loginErrorUrl(reason: Reason, next: string): string {
  const params = new URLSearchParams({ error: reason });
  if (next !== "/") params.set("next", next);
  return `/login?${params.toString()}`;
}
