import { describe, expect, it } from "vitest";

import { familyLabel, groupByFamily } from "../src/lib/families";
import type { ModelSummary } from "../src/lib/types";

function model(family: string, slug: string, over: Partial<ModelSummary> = {}): ModelSummary {
  return {
    slug,
    name: slug,
    family,
    context_window: null,
    min_output_price_cny: null,
    min_output_price_usd: null,
    has_free: false,
    price_count: 1,
    ...over,
  };
}

describe("groupByFamily", () => {
  it("orders known families first, unknown ones alphabetically after", () => {
    const groups = groupByFamily([
      model("zeta", "z1"),
      model("gpt", "g1"),
      model("alpha", "a1"),
      model("deepseek", "d1"),
    ]);
    expect(groups.map((g) => g.family)).toEqual(["deepseek", "gpt", "alpha", "zeta"]);
  });

  it("summarizes free count and cheapest price, preferring CNY", () => {
    const [group] = groupByFamily([
      model("qwen", "a", { min_output_price_usd: "0.5", has_free: true }),
      model("qwen", "b", { min_output_price_cny: "2.8000", min_output_price_usd: "0.2" }),
      model("qwen", "c", { min_output_price_cny: "1.2000" }),
    ]);
    expect(group?.models).toHaveLength(3);
    expect(group?.freeCount).toBe(1);
    expect(group?.cheapest).toEqual({ price: "1.2000", currency: "CNY" });
  });

  it("falls back to USD and to null", () => {
    const groups = groupByFamily([
      model("gpt", "a", { min_output_price_usd: "1.10" }),
      model("gpt", "b", { min_output_price_usd: "0.40" }),
      model("grok", "c"),
    ]);
    expect(groups[0]?.cheapest).toEqual({ price: "0.40", currency: "USD" });
    expect(groups[1]?.cheapest).toBeNull();
  });
});

describe("familyLabel", () => {
  it("uses friendly names with an uppercase fallback", () => {
    expect(familyLabel("qwen")).toBe("通义千问 Qwen");
    expect(familyLabel("newco")).toBe("NEWCO");
  });
});
