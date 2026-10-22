import type { APIRoute } from "astro";

import { internalSend } from "../../lib/api";
import { logger } from "../../lib/logger";
import { SESSION_COOKIE, clearSessionCookie } from "../../lib/session";

// 只接受 POST（表单提交），避免被第三方页面用一个链接或图片触发退出
export const POST: APIRoute = async ({ cookies, redirect }) => {
  const token = cookies.get(SESSION_COOKIE)?.value;
  if (token) {
    try {
      await internalSend("DELETE", "/auth/session", { sessionToken: token });
    } catch (err) {
      logger.warn({ err }, "logout: backend session delete failed");
    }
  }
  clearSessionCookie(cookies);
  return redirect("/", 303);
};
