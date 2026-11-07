// @ts-check
import node from "@astrojs/node";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, envField } from "astro/config";

export default defineConfig({
  // canonical、sitemap 等绝对地址的前缀；域名确定后在 .env 中设置 SITE_URL
  site: process.env.SITE_URL ?? "http://127.0.0.1:4321",
  output: "server",
  adapter: node({ mode: "standalone" }),
  // React 组件默认只在服务端渲染成 HTML；只有显式标 client:* 的交互岛才下发 JS 和 props
  integrations: [react()],
  server: {
    host: process.env.WEB_HOST ?? "127.0.0.1",
    port: Number(process.env.WEB_PORT ?? 4321),
  },
  prefetch: { prefetchAll: false, defaultStrategy: "hover" },
  vite: {
    plugins: [tailwindcss()],
  },
  // 除 SITE_URL（上面的 site，构建时写进产物）外都在运行时读取（server + secret），
  // 同一个镜像换环境只改 .env，不用重新构建
  env: {
    schema: {
      API_INTERNAL_URL: envField.string({
        context: "server",
        access: "secret",
        default: "http://127.0.0.1:8100",
      }),
      INTERNAL_API_TOKEN: envField.string({ context: "server", access: "secret" }),
      REDIS_URL: envField.string({
        context: "server",
        access: "secret",
        default: "redis://127.0.0.1:6379/6",
      }),
      REDIS_KEY_PREFIX: envField.string({
        context: "server",
        access: "secret",
        default: "52tokens:",
      }),
      // 只有部署在可信反代之后才设置，例如 Cloudflare 的 cf-connecting-ip
      TRUSTED_IP_HEADER: envField.string({ context: "server", access: "secret", optional: true }),
      RATE_LIMIT_PER_MINUTE: envField.number({
        context: "server",
        access: "secret",
        default: 120,
      }),
      // SCC 微信扫码回调页所在的源（即 SCC 的 WX_OPEN_REDIRECT_URI 的源），
      // 登录页只接受来自这个源的 postMessage。只在服务端渲染时写进 HTML 属性，不需要打进客户端代码
      WECHAT_CALLBACK_ORIGIN: envField.string({
        context: "server",
        access: "secret",
        default: "https://wxauth.11xy.cn",
      }),
      // Turnstile 站点 key 本身是公开的；同样只在服务端渲染时写进 data-sitekey
      TURNSTILE_SITE_KEY: envField.string({
        context: "server",
        access: "secret",
        default: "1x00000000000000000000AA",
      }),
    },
  },
});
