export interface SitemapEntry {
  loc: string;
  /** ISO 时间；只在有真实更新时间时提供，不伪造 */
  lastmod?: string;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function buildSitemap(entries: SitemapEntry[]): string {
  const urls = entries.map((e) => {
    const lastmod = e.lastmod ? `<lastmod>${escapeXml(e.lastmod)}</lastmod>` : "";
    return `  <url><loc>${escapeXml(e.loc)}</loc>${lastmod}</url>`;
  });
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...urls,
    "</urlset>",
    "",
  ].join("\n");
}
