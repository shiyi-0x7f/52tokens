import type { APIRoute } from "astro";

import { internalSend, isNotFound } from "../../../lib/api";
import { refererPath } from "../../../lib/outbound";

interface RedirectOut {
  url: string;
  is_promoted: boolean;
}

// 「去参与」出站跳转：后端记一次点击并给出落地地址（有推广链接用推广链接）。
// robots.txt 禁止抓取 /go/，入口链接带 nofollow，避免爬虫刷点击
export const GET: APIRoute = async ({ params, request, site, rewrite }) => {
  let target: RedirectOut | null;
  try {
    target = await internalSend<RedirectOut>(
      "POST",
      `/outbound/deals/${encodeURIComponent(params.slug ?? "")}`,
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
