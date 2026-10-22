import type { APIRoute } from "astro";

import { internalSend } from "../../lib/api";
import { WECHAT_STATE_COOKIE, reasonFromError, setFlowCookie } from "../../lib/session";

/**
 * 在弹窗里打开：向 SCC 取微信扫码链接后跳转。扫码完成后 SCC 回调页会用 postMessage
 * 把 code + state 发回打开弹窗的登录页。state 写进本浏览器 Cookie，提交时比对。
 */
export const GET: APIRoute = async ({ cookies, redirect }) => {
  try {
    const data = await internalSend<{ authorize_url: string; state: string }>(
      "POST",
      "/auth/wechat/start",
    );
    if (!data) throw new Error("empty wechat start response");
    setFlowCookie(cookies, WECHAT_STATE_COOKIE, data.state);
    return redirect(data.authorize_url, 302);
  } catch (err) {
    const reason = reasonFromError(err);
    return new Response(
      `<!doctype html><meta charset="utf-8"><title>微信登录</title>
<p>暂时无法发起微信登录，请关闭此窗口后重试。（${reason}）</p>`,
      { status: 502, headers: { "Content-Type": "text/html; charset=utf-8" } },
    );
  }
};
