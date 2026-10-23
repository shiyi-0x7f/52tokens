/**
 * RSS 2.0 输出。按数据防护口径只放「标题 + 链接 + 一句摘要」，不放结构化的价格 / 额度字段
 * （见 dev_docs/architecture/data-protection.md 第 2 节）。
 */
import { CYCLE_LABELS, DEAL_TYPE_LABELS } from "./labels";
import type { Deal } from "./types";
import { escapeXml } from "./xml";

/** 每个 feed 最多放的条数 */
export const RSS_LIMIT = 30;

export interface RssItem {
  title: string;
  link: string;
  description: string;
  /** ISO 时间 */
  pubDate: string;
}

export interface RssChannel {
  title: string;
  /** 对应的网页 */
  link: string;
  description: string;
  /** feed 自身地址 */
  selfUrl: string;
  items: RssItem[];
}

export function dealToRssItem(deal: Deal, site: URL): RssItem {
  const cycle = deal.cycle === "once" ? "" : `，${CYCLE_LABELS[deal.cycle]}`;
  return {
    title: `${deal.platform.name}：${deal.title}`,
    link: new URL(`/deals/${deal.slug}`, site).href,
    description: `${DEAL_TYPE_LABELS[deal.deal_type]}，${deal.reward_text}${cycle}。`,
    pubDate: deal.confirmed_at,
  };
}

export function buildRss(channel: RssChannel): string {
  const latest = channel.items
    .map((i) => i.pubDate)
    .sort()
    .at(-1);
  const items = channel.items.map((i) =>
    [
      "    <item>",
      `      <title>${escapeXml(i.title)}</title>`,
      `      <link>${escapeXml(i.link)}</link>`,
      `      <guid isPermaLink="true">${escapeXml(i.link)}</guid>`,
      `      <description>${escapeXml(i.description)}</description>`,
      `      <pubDate>${new Date(i.pubDate).toUTCString()}</pubDate>`,
      "    </item>",
    ].join("\n"),
  );
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    "  <channel>",
    `    <title>${escapeXml(channel.title)}</title>`,
    `    <link>${escapeXml(channel.link)}</link>`,
    `    <description>${escapeXml(channel.description)}</description>`,
    "    <language>zh-CN</language>",
    `    <atom:link href="${escapeXml(channel.selfUrl)}" rel="self" type="application/rss+xml" />`,
    ...(latest ? [`    <lastBuildDate>${new Date(latest).toUTCString()}</lastBuildDate>`] : []),
    ...items,
    "  </channel>",
    "</rss>",
    "",
  ].join("\n");
}

export function rssResponse(channel: RssChannel): Response {
  return new Response(buildRss(channel), {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=0, s-maxage=1800",
    },
  });
}
