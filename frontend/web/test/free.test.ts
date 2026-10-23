import { describe, expect, it } from "vitest";

import { buildFreeGuide } from "../src/lib/free";
import type { Deal, ModelDetail, Price } from "../src/lib/types";

function price(platform: string, over: Partial<Price> = {}): Price {
  return {
    platform: { slug: platform, name: platform.toUpperCase() },
    currency: "CNY",
    input_price: "1.0000",
    output_price: "2.0000",
    cache_read_price: null,
    is_free: false,
    free_note: "",
    source_url: `https://${platform}.example.com/pricing`,
    confirmed_at: "2026-10-22T02:00:00Z",
    ...over,
  };
}

function deal(slug: string, platform: string, over: Partial<Deal> = {}): Deal {
  return {
    slug,
    title: slug,
    deal_type: "signup_credit",
    platform: { slug: platform, name: platform.toUpperCase() },
    reward_text: "100 万 tokens",
    est_value_cny: null,
    requirements: [],
    cycle: "once",
    starts_at: null,
    ends_at: null,
    description: "",
    steps: [],
    is_promoted: false,
    source_url: "https://x.example.com",
    source_quote: "",
    source_locate_url: "https://x.example.com",
    in_app_only: false,
    confirmed_at: "2026-10-22T02:00:00Z",
    is_expired: false,
    ...over,
  };
}

function model(prices: Price[]): ModelDetail {
  return {
    slug: "qwen3-8b",
    name: "Qwen3-8B",
    family: "qwen",
    context_window: 131072,
    description: "",
    prices,
  };
}

describe("buildFreeGuide", () => {
  it("lists free channels and cheapest paid prices in one currency", () => {
    const guide = buildFreeGuide(
      model([
        price("siliconflow", {
          is_free: true,
          input_price: null,
          output_price: null,
          free_note: "限速",
        }),
        price("bailian", { output_price: "3.0000" }),
        price("ark", { output_price: "1.5000" }),
        price("openrouter", { currency: "USD", output_price: "0.1000" }),
        price("zero", { output_price: "0.0000" }),
      ]),
      [],
    );
    expect(guide.freePrices.map((p) => p.platform.slug)).toEqual(["siliconflow"]);
    expect(guide.cheapestPaid.map((p) => p.platform.slug)).toEqual(["ark", "bailian"]);
    expect(guide.indexable).toBe(true);
    expect(guide.faq[0]?.a).toContain(
      "SILICONFLOW 可以免费调用 Qwen3-8B，通常有请求频率或用量上限",
    );
    expect(guide.faq[1]?.a).toContain("ARK 最便宜，输出 ¥1.50");
  });

  it("keeps only active free-type deals from platforms that serve the model", () => {
    const guide = buildFreeGuide(model([price("bailian"), price("ark")]), [
      deal("bailian-signup", "bailian"),
      deal("bailian-signup", "bailian"), // 重复
      deal("ark-quota", "ark", { deal_type: "free_quota" }),
      deal("ark-checkin", "ark", { deal_type: "checkin_points" }),
      deal("ark-old", "ark", { is_expired: true }),
      deal("other-signup", "other"),
    ]);
    expect(guide.deals.map((d) => d.slug)).toEqual(["bailian-signup", "ark-quota"]);
    expect(guide.indexable).toBe(true);
    expect(guide.faq[0]?.a).toContain("目前没有长期免费的渠道，但 BAILIAN、ARK 有免费额度");
  });

  it("is not indexable without free channels or deals", () => {
    const guide = buildFreeGuide(model([price("bailian")]), []);
    expect(guide.indexable).toBe(false);
    expect(guide.faq[0]?.a).toContain("目前没有找到");
  });

  it("falls back to USD when there is no CNY paid price", () => {
    const guide = buildFreeGuide(
      model([price("openrouter", { currency: "USD", output_price: "0.2000" })]),
      [],
    );
    expect(guide.cheapestPaid.map((p) => p.currency)).toEqual(["USD"]);
    expect(guide.faq).toHaveLength(2);
  });
});
