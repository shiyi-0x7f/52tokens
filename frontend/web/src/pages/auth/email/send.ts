import { TRUSTED_IP_HEADER } from "astro:env/server";
import type { APIRoute } from "astro";

import { internalSend } from "../../../lib/api";
import { safeNext } from "../../../lib/next-path";
import { resolveClientIp } from "../../../lib/rate-limit";
import {
  PENDING_EMAIL_COOKIE,
  loginErrorUrl,
  reasonFromError,
  setFlowCookie,
} from "../../../lib/session";

// 第一步：校验人机验证并发送邮箱验证码；邮箱暂存在短期 Cookie 里，不放进 URL
export const POST: APIRoute = async ({ request, cookies, redirect, clientAddress }) => {
  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim();
  const next = safeNext(String(form.get("next") ?? "/"));
  try {
    await internalSend("POST", "/auth/email/send", {
      body: {
        email,
        turnstile_token: String(form.get("cf-turnstile-response") ?? "") || null,
        remote_ip: resolveClientIp(request.headers, clientAddress, TRUSTED_IP_HEADER),
      },
    });
    setFlowCookie(cookies, PENDING_EMAIL_COOKIE, email.toLowerCase());
    const params = new URLSearchParams({ step: "code" });
    if (next !== "/") params.set("next", next);
    return redirect(`/login?${params.toString()}`, 303);
  } catch (err) {
    return redirect(loginErrorUrl(reasonFromError(err), next), 303);
  }
};
