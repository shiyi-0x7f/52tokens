import { describe, expect, it } from "vitest";

import { formatContext, formatMinOutput, formatPrice, formatRelative } from "../src/lib/format";

describe("formatMinOutput", () => {
  it("prefers CNY and falls back to USD", () => {
    expect(formatMinOutput({ min_output_price_cny: "3.0000", min_output_price_usd: "0.5" })).toBe(
      "¥3.00",
    );
    expect(formatMinOutput({ min_output_price_cny: null, min_output_price_usd: "1.1000" })).toBe(
      "$1.10",
    );
    expect(formatMinOutput({ min_output_price_cny: null, min_output_price_usd: null })).toBe("—");
  });
});

describe("formatPrice", () => {
  it("keeps two decimals and trims trailing zeros beyond that", () => {
    expect(formatPrice("2.8000", "CNY")).toBe("¥2.80");
    expect(formatPrice("0.0700", "USD")).toBe("$0.07");
    expect(formatPrice("0.1250", "USD")).toBe("$0.125");
    expect(formatPrice("3", "CNY")).toBe("¥3.00");
  });

  it("renders missing values as a dash", () => {
    expect(formatPrice(null, "CNY")).toBe("—");
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-10-22T12:00:00Z");

  it("uses minutes, hours and days", () => {
    expect(formatRelative("2026-10-22T11:59:30Z", now)).toBe("刚刚");
    expect(formatRelative("2026-10-22T11:48:00Z", now)).toBe("12 分钟前");
    expect(formatRelative("2026-10-22T09:00:00Z", now)).toBe("3 小时前");
    expect(formatRelative("2026-10-19T12:00:00Z", now)).toBe("3 天前");
  });

  it("falls back to a date after 30 days", () => {
    expect(formatRelative("2026-08-01T12:00:00Z", now)).toBe("2026/08/01");
  });
});

describe("formatContext", () => {
  it("abbreviates thousands", () => {
    expect(formatContext(131072)).toBe("131K");
    expect(formatContext(null)).toBe("—");
  });
});
