import type { APIRoute } from "astro";

import { internalSend } from "../../../lib/api";
import { safeNext } from "../../../lib/next-path";
import {
  GOOGLE_STATE_COOKIE,
  type SessionData,
  loginErrorUrl,
  reasonFromError,
  setSessionCookie,
  takeFlowCookie,
} from "../../../lib/session";

// Google 回调：校验 state 属于本浏览器，再交给后端完成登录，会话写入 httpOnly Cookie
export const GET: APIRoute = async ({ url, cookies, redirect }) => {
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const expected = takeFlowCookie(cookies, GOOGLE_STATE_COOKIE);
  if (url.searchParams.get("error") || !code || !state) {
    return redirect(loginErrorUrl("cancelled", "/"), 302);
  }
  if (!expected || expected !== state) {
    // 不是本浏览器发起的登录（或已过期），可能是登录 CSRF
    return redirect(loginErrorUrl("expired", "/"), 302);
  }
  try {
    const data = await internalSend<SessionData>("POST", "/auth/google/callback", {
      body: { code, state },
    });
    if (!data) return redirect(loginErrorUrl("failed", "/"), 302);
    setSessionCookie(cookies, data.session_token, data.expires_in);
    return redirect(safeNext(data.next), 302);
  } catch (err) {
    return redirect(loginErrorUrl(reasonFromError(err), "/"), 302);
  }
};
