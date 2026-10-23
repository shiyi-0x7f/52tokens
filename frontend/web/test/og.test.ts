import { describe, expect, it } from "vitest";

import { DEFAULT_CARD, dealCard, modelCard, platformCard } from "../src/lib/og/cards";
import { renderOgPng } from "../src/lib/og/render";
import type { Deal, ModelDetail, Price } from "../src/lib/types";

const deal: Deal = {
  slug: "trae-daily-checkin",
  title: "每日签到送积分",
  deal_type: "checkin_points",
  platform: { slug: "trae", name: "Trae" },
  reward_text: "+200 积分/天",
  est_value_cny: null,
  requirements: ["需登录", "需手机号", "需实名", "第四项"],
  cycle: "daily",
  starts_at: null,
  ends_at: null,
  description: "",
  steps: [],
  is_promoted: false,
  source_url: "https://www.trae.ai",
  source_quote: "",
  source_locate_url: "https://www.trae.ai",
  in_app_only: true,
  confirmed_at: "2026-10-22T02:00:00Z",
  is_expired: false,
};

function price(over: Partial<Price>): Price {
  return {
    platform: { slug: "x", name: "X" },
    currency: "CNY",
    input_price: "1.0000",
    output_price: "2.0000",
    cache_read_price: null,
    is_free: false,
    free_note: "",
    source_url: "https://x.example.com",
    confirmed_at: "2026-10-22T02:00:00Z",
    ...over,
  };
}

describe("cards", () => {
  it("deal card shows platform, reward and up to 3 requirements", () => {
    expect(dealCard(deal)).toEqual({
      eyebrow: "Trae · 签到",
      title: "每日签到送积分",
      highlight: "+200 积分/天",
      note: "每日 · 需在客户端内完成",
      tags: ["需登录", "需手机号", "需实名"],
    });
  });

  it("model card uses the lowest paid price in one currency", () => {
    const model: ModelDetail = {
      slug: "qwen3-8b",
      name: "Qwen3-8B",
      family: "qwen",
      context_window: null,
      description: "",
      prices: [
        price({ output_price: "3.0000" }),
        price({ output_price: "1.2000" }),
        price({ currency: "USD", output_price: "0.0500" }),
        price({ is_free: true, output_price: null }),
      ],
    };
    const card = modelCard(model);
    expect(card.highlight).toBe("输出 ¥1.20 / 百万 tokens 起");
    expect(card.note).toBe("4 个平台比价");
    expect(card.tags).toEqual(["1 个免费渠道"]);
  });

  it("platform card counts active deals", () => {
    const platform = {
      slug: "trae",
      name: "Trae",
      category: "coding_tool" as const,
      website_url: "https://www.trae.ai",
      description: "",
    };
    expect(
      platformCard(platform, [deal, { ...deal, slug: "b", deal_type: "trial" }]),
    ).toMatchObject({
      title: "Trae",
      highlight: "2 个进行中的活动",
      tags: ["签到", "试用"],
    });
    expect(platformCard(platform, []).highlight).toBeUndefined();
  });
});

describe("renderOgPng", () => {
  it("renders a 1200x630 PNG with the Chinese font", async () => {
    const png = await renderOgPng(dealCard(deal));
    // PNG 文件头 + IHDR 里的宽高
    expect([...png.slice(0, 8)]).toEqual([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    const view = new DataView(png.buffer, png.byteOffset);
    expect(view.getUint32(16)).toBe(1200);
    expect(view.getUint32(20)).toBe(630);
  });

  it("renders the default card", async () => {
    const png = await renderOgPng(DEFAULT_CARD);
    expect(png.length).toBeGreaterThan(5000);
  });
});
