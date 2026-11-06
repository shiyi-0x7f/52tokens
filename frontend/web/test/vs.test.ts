import { describe, expect, it } from "vitest";

import type { ModelDetail, Price } from "../src/lib/types";
import { buildVsSummary, vsPath } from "../src/lib/vs";

function price(over: Partial<Price> = {}): Price {
  return {
    platform: { slug: "openrouter", name: "OpenRouter" },
    currency: "USD",
    input_price: "1.0000",
    output_price: "4.0000",
    cache_read_price: null,
    is_free: false,
    free_note: "",
    source_url: "https://x",
    confirmed_at: "2026-11-01T00:00:00Z",
    ...over,
  };
}

function model(name: string, prices: Price[], over: Partial<ModelDetail> = {}): ModelDetail {
  return {
    slug: name.toLowerCase(),
    name,
    family: "x",
    context_window: 128000,
    description: "",
    prices,
    ...over,
  };
}

describe("vsPath", () => {
  it("按收录顺序拼网址", () => {
    expect(vsPath("deepseek-v3-2", "qwen3-max")).toBe("/models/deepseek-v3-2-vs-qwen3-max");
  });
});

describe("buildVsSummary", () => {
  it("同币种时指出更便宜的一方和便宜的比例", () => {
    const a = model("A", [price({ output_price: "1.0000", input_price: "0.5000" })]);
    const b = model("B", [price({ output_price: "4.0000", input_price: "0.5000" })]);
    const { highlights, faq } = buildVsSummary(a, b);
    expect(highlights[0]).toBe("A 的输出价更低：最低 $1.00，B 最低 $4.00，便宜约 75%。");
    expect(highlights[1]).toBe("两者最低输入价相同，都是 $0.50 / 百万 tokens。");
    expect(faq[0]?.q).toBe("A 和 B 哪个 API 更便宜？");
  });

  it("币种不同不比较高低", () => {
    const a = model("A", [price({ currency: "CNY", output_price: "8.0000" })]);
    const b = model("B", [price({ output_price: "2.0000" })]);
    expect(buildVsSummary(a, b).highlights[0]).toBe(
      "最低输出价：A ¥8.00，B $2.00（币种不同，未换算）。",
    );
  });

  it("上下文与免费渠道", () => {
    const a = model("A", [price({ is_free: true })], { context_window: 1_000_000 });
    const b = model("B", [price()], { context_window: 128000 });
    const { highlights, faq } = buildVsSummary(a, b);
    expect(highlights).toContain("A 的上下文更长：1000K，B 为 128K。");
    expect(highlights).toContain("只有 A 有免费可用的渠道（通常有频率限制）。");
    expect(faq.map((f) => f.q)).toEqual([
      "A 和 B 哪个 API 更便宜？",
      "A 和 B 哪个上下文更长？",
      "A 和 B 有免费的 API 吗？",
    ]);
  });

  it("缺少价格或上下文时略过对应的句子", () => {
    const a = model("A", [], { context_window: null });
    const b = model("B", [price()], { context_window: null });
    const { highlights, faq } = buildVsSummary(a, b);
    expect(highlights[0]).toBe("只有 B 有付费输出价数据：最低 $4.00 / 百万 tokens。");
    expect(faq.some((f) => f.q.includes("上下文"))).toBe(false);
  });
});
