import type { APIRoute } from "astro";

import { internalSend } from "../../../lib/api";
import { safeNext } from "../../../lib/next-path";
import {
  PENDING_EMAIL_COOKIE,
  type SessionData,
  loginErrorUrl,
  reasonFromError,
  setSessionCookie,
} from "../../../lib/session";

// 第二步：用验证码登录。验证码错误时保留待验证邮箱，方便直接重填
export const POST: APIRoute = async ({ request, cookies, redirect }) => {
  const form = await request.formData();
  const code = String(form.get("code") ?? "").trim();
  const next = safeNext(String(form.get("next") ?? "/"));
  const email = cookies.get(PENDING_EMAIL_COOKIE)?.value;
  if (!email) return redirect(loginErrorUrl("expired", next), 303);
  try {
    const data = await internalSend<SessionData>("POST", "/auth/email/login", {
      body: { email, code },
    });
    if (!data) return redirect(loginErrorUrl("failed", next), 303);
    cookies.delete(PENDING_EMAIL_COOKIE, { path: "/" });
    setSessionCookie(cookies, data.session_token, data.expires_in);
    return redirect(next, 303);
  } catch (err) {
    const reason = reasonFromError(err);
    const params = new URLSearchParams({ error: reason });
    if (reason === "code_invalid") params.set("step", "code");
    if (next !== "/") params.set("next", next);
    return redirect(`/login?${params.toString()}`, 303);
  }
};
