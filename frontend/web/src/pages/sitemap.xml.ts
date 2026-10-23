import type { APIRoute } from "astro";

import { internalGet } from "../lib/api";
import { buildSitemap, type SitemapEntry } from "../lib/sitemap";
import type { Deal, ModelSummary } from "../lib/types";

const STATIC_PATHS = ["/", "/models", "/free", "/deals", "/platforms"];

export const GET: APIRoute = async ({ site }) => {
  const base = site ?? new URL("http://127.0.0.1:4321");
  const [models, deals] = await Promise.all([
    internalGet<ModelSummary[]>("/models"),
    // 已结束的活动页面保留，同样进 sitemap
    internalGet<Deal[]>("/deals", { include_expired: true, limit: 100 }),
  ]);
  // 平台页只收有活动的平台（没有活动的平台页是 noindex），lastmod 取其活动最近的核实时间
  const platformLastmod = new Map<string, string>();
  for (const d of deals) {
    const prev = platformLastmod.get(d.platform.slug);
    if (!prev || d.confirmed_at > prev) platformLastmod.set(d.platform.slug, d.confirmed_at);
  }
  const entries: SitemapEntry[] = [
    ...STATIC_PATHS.map((path) => ({ loc: new URL(path, base).href })),
    ...models.map((m) => ({ loc: new URL(`/models/${m.slug}`, base).href })),
    // 免费页只收有免费渠道的模型；其余模型的免费页可能是 noindex
    ...models
      .filter((m) => m.has_free)
      .map((m) => ({ loc: new URL(`/free/${m.slug}`, base).href })),
    ...deals.map((d) => ({ loc: new URL(`/deals/${d.slug}`, base).href, lastmod: d.confirmed_at })),
    ...[...platformLastmod].map(([slug, lastmod]) => ({
      loc: new URL(`/platforms/${slug}`, base).href,
      lastmod,
    })),
  ];
  return new Response(buildSitemap(entries), {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=0, s-maxage=3600",
    },
  });
};
