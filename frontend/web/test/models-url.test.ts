import { describe, expect, it } from "vitest";

import {
  MAX_COMPARE,
  compareUrl,
  modelsUrl,
  parseCompare,
  parseFamily,
  parseQuery,
  toggleCompare,
} from "../src/lib/models-url";

describe("parseCompare", () => {
  it("validates, dedupes and caps the list", () => {
    expect(parseCompare("a-1,b,a-1,<x>,C,d,e,f")).toEqual(["a-1", "b", "d", "e"]);
    expect(parseCompare(null)).toEqual([]);
  });
});

describe("toggleCompare", () => {
  it("adds, removes and refuses when full", () => {
    expect(toggleCompare(["a"], "b")).toEqual(["a", "b"]);
    expect(toggleCompare(["a", "b"], "a")).toEqual(["b"]);
    const full = ["a", "b", "c", "d"];
    expect(full).toHaveLength(MAX_COMPARE);
    expect(toggleCompare(full, "e")).toEqual(full);
  });
});

describe("parseFamily / parseQuery", () => {
  it("rejects unsafe values and trims queries", () => {
    expect(parseFamily("gpt")).toBe("gpt");
    expect(parseFamily("<script>")).toBeNull();
    expect(parseQuery("  flash ")).toBe("flash");
    expect(parseQuery("   ")).toBeNull();
    expect(parseQuery("x".repeat(80))).toHaveLength(50);
  });
});

describe("urls", () => {
  it("builds models urls, search taking precedence over family", () => {
    expect(modelsUrl({})).toBe("/models");
    expect(modelsUrl({ family: "gpt", cmp: ["a", "b"] })).toBe("/models?family=gpt&cmp=a%2Cb");
    expect(modelsUrl({ family: "gpt", q: "flash" })).toBe("/models?q=flash");
  });

  it("builds compare urls", () => {
    expect(compareUrl(["a", "b"])).toBe("/models/compare?m=a%2Cb");
    expect(compareUrl(["a", "b"], true)).toBe("/models/compare?m=a%2Cb&diff=1");
  });
});
