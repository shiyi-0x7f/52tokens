// @ts-check
import node from "@astrojs/node";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, envField } from "astro/config";

export default defineConfig({
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
        access: "public",
        default: "52tokens:",
      }),
      // 只有部署在可信反代之后才设置，例如 Cloudflare 的 cf-connecting-ip
      TRUSTED_IP_HEADER: envField.string({ context: "server", access: "public", optional: true }),
      RATE_LIMIT_PER_MINUTE: envField.number({
        context: "server",
        access: "public",
        default: 120,
      }),
      TURNSTILE_SITE_KEY: envField.string({
        context: "client",
        access: "public",
        default: "1x00000000000000000000AA",
      }),
    },
  },
});
