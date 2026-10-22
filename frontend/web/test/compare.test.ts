import { describe, expect, it } from "vitest";

import { buildCompareRows } from "../src/lib/compare";
import type { ModelDetail, Price } from "../src/lib/types";

const NOW = new Date("2026-10-22T12:00:00Z");

function price(platform: string, over: Partial<Price> = {}): Price {
  return {
    platform: { slug: platform, name: platform.toUpperCase() },
    currency: "USD",
    input_price: "1.0000",
    output_price: "2.0000",
    cache_read_price: null,
    is_free: false,
    free_note: "",
    source_url: "https://x",
    confirmed_at: "2026-10-22T09:00:00Z",
    ...over,
  };
}

function model(slug: string, prices: Price[], over: Partial<ModelDetail> = {}): ModelDetail {
  return {
    slug,
    name: slug,
    family: "gpt",
    context_window: 128000,
    description: "",
    prices,
    ...over,
  };
}

const row = (rows: ReturnType<typeof buildCompareRows>, label: string) => {
  const found = rows.find((r) => r.label === label);
  if (!found) throw new Error(`row ${label} missing`);
  return found;
};

describe("buildCompareRows", () => {
  it("highlights the cheapest output price and the largest context", () => {
    const rows = buildCompareRows(
      [
        model("a", [price("openrouter", { output_price: "3.0000" })], {
          context_window: 1_000_000,
        }),
        model("b", [price("openrouter", { output_price: "1.5000" })]),
      ],
      NOW,
    );
    const output = row(rows, "最低输出价");
    expect(output.cells.map((c) => c.text)).toEqual(["$3.00", "$1.50"]);
    expect(output.cells.map((c) => c.best)).toEqual([false, true]);
    expect(row(rows, "上下文窗口").cells.map((c) => c.best)).toEqual([true, false]);
  });

  it("only compares within the majority currency", () => {
    const rows = buildCompareRows(
      [
        model("a", [price("deepseek", { currency: "CNY", output_price: "3.0000" })]),
        model("b", [price("kimi", { currency: "CNY", output_price: "8.0000" })]),
        model("c", [price("openrouter", { output_price: "0.1000" })]),
      ],
      NOW,
    );
    expect(row(rows, "最低输出价").cells.map((c) => c.best)).toEqual([true, false, false]);
  });

  it("lists every platform and marks rows with identical values", () => {
    const rows = buildCompareRows(
      [
        model("a", [
          price("openrouter"),
          price("siliconflow", { is_free: true, output_price: null }),
        ]),
        model("b", [price("openrouter")]),
      ],
      NOW,
    );
    expect(row(rows, "OPENROUTER").same).toBe(true);
    expect(row(rows, "SILICONFLOW").cells.map((c) => c.text)).toEqual(["免费", "—"]);
    expect(row(rows, "系列").same).toBe(true);
    expect(row(rows, "免费渠道").cells.map((c) => c.best)).toEqual([true, false]);
    expect(row(rows, "最近核实").cells[0]?.text).toBe("3 小时前");
  });

  it("does not mark a winner when values tie", () => {
    const rows = buildCompareRows([model("a", [price("x")]), model("b", [price("x")])], NOW);
    expect(row(rows, "上下文窗口").cells.every((c) => !c.best)).toBe(true);
    expect(row(rows, "最低输出价").cells.every((c) => !c.best)).toBe(true);
  });
});
