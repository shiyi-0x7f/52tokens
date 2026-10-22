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
  const entries: SitemapEntry[] = [
    ...STATIC_PATHS.map((path) => ({ loc: new URL(path, base).href })),
    ...models.map((m) => ({ loc: new URL(`/models/${m.slug}`, base).href })),
    ...deals.map((d) => ({ loc: new URL(`/deals/${d.slug}`, base).href, lastmod: d.confirmed_at })),
  ];
  return new Response(buildSitemap(entries), {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=0, s-maxage=3600",
    },
  });
};
