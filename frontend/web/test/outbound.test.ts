import { describe, expect, it } from "vitest";

import { dealGoUrl, refererPath } from "../src/lib/outbound";

const SITE = new URL("https://52tokens.example.com");

describe("dealGoUrl", () => {
  it("encodes the slug", () => {
    expect(dealGoUrl("trae-checkin")).toBe("/go/deal/trae-checkin");
    expect(dealGoUrl("a/b")).toBe("/go/deal/a%2Fb");
  });
});

describe("refererPath", () => {
  it("keeps only the path of same-site referers", () => {
    expect(refererPath("https://52tokens.example.com/deals/x?from=rss#top", SITE)).toBe("/deals/x");
  });

  it.each([
    [null],
    [""],
    ["not a url"],
    ["https://evil.example.com/deals/x"],
    ["http://52tokens.example.com/deals/x"],
  ])("ignores %s", (referer) => {
    expect(refererPath(referer, SITE)).toBe("");
  });

  it("truncates long paths", () => {
    const long = `https://52tokens.example.com/${"a".repeat(300)}`;
    expect(refererPath(long, SITE)).toHaveLength(200);
  });
});
