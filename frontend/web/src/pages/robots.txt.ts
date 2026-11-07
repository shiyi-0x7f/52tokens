import type { APIRoute } from "astro";

// AI 爬虫是否放行尚待决定（见 data-protection.md 第 7 节），目前与普通爬虫一致
export const GET: APIRoute = ({ site }) => {
  const sitemap = new URL("/sitemap.xml", site).href;
  const body = [
    "User-agent: *",
    "Allow: /",
    // 不列后台路径：robots.txt 是公开的，列出来等于告诉别人后台在哪（后台页面本身是 noindex 的 SPA）
    "Disallow: /auth/",
    "Disallow: /go/",
    "",
    `Sitemap: ${sitemap}`,
    "",
  ];
  return new Response(body.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
