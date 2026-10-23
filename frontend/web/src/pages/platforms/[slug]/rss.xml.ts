import type { APIRoute } from "astro";

import { internalGet, isNotFound } from "../../../lib/api";
import { RSS_LIMIT, dealToRssItem, rssResponse } from "../../../lib/rss";
import type { Deal, Platform } from "../../../lib/types";

// 单个平台进行中的活动
export const GET: APIRoute = async ({ params, site, rewrite }) => {
  const base = site ?? new URL("http://127.0.0.1:4321");
  const slug = params.slug ?? "";
  let platform: Platform;
  try {
    platform = await internalGet<Platform>(`/platforms/${encodeURIComponent(slug)}`);
  } catch (err) {
    if (isNotFound(err)) return rewrite("/404");
    throw err;
  }
  const deals = await internalGet<Deal[]>("/deals", { platform: platform.slug, limit: RSS_LIMIT });
  return rssResponse({
    title: `52tokens · ${platform.name} 优惠活动`,
    link: new URL(`/platforms/${platform.slug}`, base).href,
    description: `${platform.name} 的签到积分、免费额度、注册赠送等活动，官网核实后更新。`,
    selfUrl: new URL(`/platforms/${platform.slug}/rss.xml`, base).href,
    items: deals.map((d) => dealToRssItem(d, base)),
  });
};
