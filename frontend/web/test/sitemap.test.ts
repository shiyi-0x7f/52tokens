import { describe, expect, it } from "vitest";

import { buildSitemap } from "../src/lib/sitemap";

describe("buildSitemap", () => {
  it("renders urls with optional lastmod and escapes xml", () => {
    const xml = buildSitemap([
      { loc: "https://x.com/" },
      { loc: "https://x.com/deals/a?b=1&c=2", lastmod: "2026-10-22T02:00:00Z" },
    ]);
    expect(xml).toContain("<url><loc>https://x.com/</loc></url>");
    expect(xml).toContain(
      "<url><loc>https://x.com/deals/a?b=1&amp;c=2</loc><lastmod>2026-10-22T02:00:00Z</lastmod></url>",
    );
    expect(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>')).toBe(true);
  });
});
