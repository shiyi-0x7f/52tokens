import { describe, expect, it } from "vitest";

import { buildRss, dealToRssItem } from "../src/lib/rss";
import type { Deal } from "../src/lib/types";

const SITE = new URL("https://52tokens.example.com");

const deal: Deal = {
  slug: "trae-daily-checkin",
  title: "每日签到 <送积分>",
  deal_type: "checkin_points",
  platform: { slug: "trae", name: "Trae & Co" },
  reward_text: "+200 积分/天",
  est_value_cny: "3.50",
  requirements: ["需登录"],
  cycle: "daily",
  starts_at: null,
  ends_at: null,
  description: "打开客户端签到",
  is_promoted: true,
  source_url: "https://www.trae.ai/events",
  in_app_only: true,
  confirmed_at: "2026-10-22T02:00:00Z",
  is_expired: false,
};

describe("dealToRssItem", () => {
  it("only carries title, link and a one-line summary", () => {
    const item = dealToRssItem(deal, SITE);
    expect(item).toEqual({
      title: "Trae & Co：每日签到 <送积分>",
      link: "https://52tokens.example.com/deals/trae-daily-checkin",
      description: "签到，+200 积分/天，每日。",
      pubDate: "2026-10-22T02:00:00Z",
    });
  });

  it("omits the cycle for one-off deals", () => {
    expect(dealToRssItem({ ...deal, cycle: "once" }, SITE).description).toBe(
      "签到，+200 积分/天。",
    );
  });
});

describe("buildRss", () => {
  const xml = buildRss({
    title: "52tokens & 活动",
    link: "https://52tokens.example.com/deals",
    description: "desc",
    selfUrl: "https://52tokens.example.com/deals/rss.xml",
    items: [
      dealToRssItem(deal, SITE),
      { ...dealToRssItem(deal, SITE), pubDate: "2026-10-23T08:00:00Z" },
    ],
  });

  it("escapes text and includes self link", () => {
    expect(xml).toContain("<title>52tokens &amp; 活动</title>");
    expect(xml).toContain("<title>Trae &amp; Co：每日签到 &lt;送积分&gt;</title>");
    expect(xml).toContain('href="https://52tokens.example.com/deals/rss.xml" rel="self"');
    expect(xml).not.toContain("<送积分>");
  });

  it("uses RFC 822 dates and the latest item as build date", () => {
    expect(xml).toContain("<pubDate>Thu, 22 Oct 2026 02:00:00 GMT</pubDate>");
    expect(xml).toContain("<lastBuildDate>Fri, 23 Oct 2026 08:00:00 GMT</lastBuildDate>");
  });

  it("leaves out structured value fields", () => {
    expect(xml).not.toContain("3.50");
    expect(xml).not.toContain("trae.ai/events");
  });

  it("has no build date when empty", () => {
    const empty = buildRss({ title: "t", link: "l", description: "d", selfUrl: "s", items: [] });
    expect(empty).not.toContain("lastBuildDate");
    expect(empty).not.toContain("<item>");
  });
});
