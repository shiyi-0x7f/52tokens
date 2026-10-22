import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 端口与后端地址来自 .env.dev（由 start-dev.sh 导出），不硬编码
const apiTarget = process.env["API_INTERNAL_URL"] ?? "http://127.0.0.1:8100";

export default defineConfig({
  base: "/admin/",
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: Number(process.env["ADMIN_PORT"] ?? 5174),
    strictPort: true,
    // dev 同源代理后台接口，避免 CORS；生产由 nginx 反代 /api/admin/*
    proxy: { "/api/admin": { target: apiTarget, changeOrigin: true } },
  },
});
