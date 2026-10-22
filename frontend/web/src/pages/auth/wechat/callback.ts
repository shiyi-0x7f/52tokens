import type { APIRoute } from "astro";

import { internalSend } from "../../../lib/api";
import { safeNext } from "../../../lib/next-path";
import {
  type SessionData,
  WECHAT_STATE_COOKIE,
  loginErrorUrl,
  reasonFromError,
  setSessionCookie,
  takeFlowCookie,
} from "../../../lib/session";

// 登录页收到 SCC 回调页的 postMessage 后，用表单 POST 到这里完成微信登录
export const POST: APIRoute = async ({ request, cookies, redirect }) => {
  const form = await request.formData();
  const code = String(form.get("code") ?? "");
  const state = String(form.get("state") ?? "");
  const next = safeNext(String(form.get("next") ?? "/"));
  const expected = takeFlowCookie(cookies, WECHAT_STATE_COOKIE);
  if (!code || !state || !expected || expected !== state) {
    return redirect(loginErrorUrl("expired", next), 303);
  }
  try {
    const data = await internalSend<SessionData>("POST", "/auth/wechat/callback", {
      body: { code, state },
    });
    if (!data) return redirect(loginErrorUrl("failed", next), 303);
    setSessionCookie(cookies, data.session_token, data.expires_in);
    return redirect(next, 303);
  } catch (err) {
    return redirect(loginErrorUrl(reasonFromError(err), next), 303);
  }
};
