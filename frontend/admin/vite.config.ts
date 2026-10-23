import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 端口与后端地址来自 .env.dev（由 start-dev.sh 导出），不硬编码
const apiTarget = process.env["API_INTERNAL_URL"] ?? "http://127.0.0.1:8100";

export default defineConfig(({ command }) => {
  // dev 下公开站和后台端口不同：把公开站地址注入后台，用于「去登录」和「查看页面」链接。
  // 生产同域，留空即可
  if (command === "serve") {
    process.env["VITE_WEB_ORIGIN"] ??= `http://127.0.0.1:${process.env["WEB_PORT"] ?? 4321}`;
  }
  return {
    base: "/admin/",
    plugins: [react()],
    // 后台只有管理员使用，Ant Design 整包约 1.4 MB（gzip 约 440 KB）可以接受，不影响公开站速度
    build: { chunkSizeWarningLimit: 1500 },
    server: {
      host: "127.0.0.1",
      port: Number(process.env["ADMIN_PORT"] ?? 5174),
      strictPort: true,
      // dev 同源代理后台接口（带上公开站写的会话 Cookie，Cookie 不区分端口）；生产由 nginx 反代
      proxy: { "/api/admin": { target: apiTarget, changeOrigin: true } },
    },
  };
});
