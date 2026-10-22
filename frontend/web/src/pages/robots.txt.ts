import type { APIRoute } from "astro";

// AI 爬虫是否放行尚待决定（见 data-protection.md 第 7 节），目前与普通爬虫一致
export const GET: APIRoute = ({ site }) => {
  const sitemap = new URL("/sitemap.xml", site).href;
  const body = [
    "User-agent: *",
    "Allow: /",
    "Disallow: /admin/",
    "Disallow: /auth/",
    "",
    `Sitemap: ${sitemap}`,
    "",
  ];
  return new Response(body.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
