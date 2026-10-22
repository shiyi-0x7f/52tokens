import type { APIRoute } from "astro";

// 轻量健康检查：不调用后端，供容器 / 反代 30s 探测
export const GET: APIRoute = () => new Response("ok");
