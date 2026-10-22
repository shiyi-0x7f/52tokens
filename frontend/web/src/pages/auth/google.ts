import type { APIRoute } from "astro";

import { internalSend } from "../../lib/api";
import { safeNext } from "../../lib/next-path";
import {
  GOOGLE_STATE_COOKIE,
  loginErrorUrl,
  reasonFromError,
  setFlowCookie,
} from "../../lib/session";

// 登录入口：后端生成 state + PKCE；state 同时写进本浏览器 Cookie，回调时比对
export const GET: APIRoute = async ({ url, cookies, redirect }) => {
  const next = safeNext(url.searchParams.get("next"));
  try {
    const data = await internalSend<{ authorize_url: string; state: string }>(
      "POST",
      "/auth/google/start",
      { body: { next } },
    );
    if (!data) return redirect(loginErrorUrl("failed", next), 302);
    setFlowCookie(cookies, GOOGLE_STATE_COOKIE, data.state);
    return redirect(data.authorize_url, 302);
  } catch (err) {
    return redirect(loginErrorUrl(reasonFromError(err), next), 302);
  }
};
