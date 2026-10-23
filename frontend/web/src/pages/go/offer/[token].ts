import type { APIRoute } from "astro";

import { internalSend, isNotFound } from "../../../lib/api";
import { refererPath } from "../../../lib/outbound";

interface RedirectOut {
  url: string;
  is_promoted: boolean;
}

// 卡网报价「去店铺」：页面上先弹窗提示这是第三方店铺，用户确认后才请求这里，
// 后端记一次点击并给出店铺链接。robots.txt 禁止抓取 /go/，入口链接带 nofollow
export const GET: APIRoute = async ({ params, request, site, rewrite }) => {
  let target: RedirectOut | null;
  try {
    target = await internalSend<RedirectOut>(
      "POST",
      `/outbound/offers/${encodeURIComponent(params.token ?? "")}`,
      {
        body: {
          referer_path: site ? refererPath(request.headers.get("Referer"), site) : "",
        },
      },
    );
  } catch (err) {
    if (isNotFound(err)) return rewrite("/404");
    throw err;
  }
  if (!target) return rewrite("/404");
  return new Response(null, {
    status: 302,
    headers: {
      Location: target.url,
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
};
