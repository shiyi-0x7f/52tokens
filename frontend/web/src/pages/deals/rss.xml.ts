import type { APIRoute } from "astro";

import { internalGet } from "../../lib/api";
import { RSS_LIMIT, dealToRssItem, rssResponse } from "../../lib/rss";
import type { Deal } from "../../lib/types";

// 全站进行中的活动，按最近核实时间倒序
export const GET: APIRoute = async ({ site }) => {
  const base = site ?? new URL("http://127.0.0.1:4321");
  const deals = await internalGet<Deal[]>("/deals", { limit: RSS_LIMIT });
  return rssResponse({
    title: "52tokens · AI 羊毛活动",
    link: new URL("/deals", base).href,
    description: "AI 工具签到积分、大模型 API 免费额度、注册赠送与限时折扣，官网核实后更新。",
    selfUrl: new URL("/deals/rss.xml", base).href,
    items: deals.map((d) => dealToRssItem(d, base)),
  });
};
