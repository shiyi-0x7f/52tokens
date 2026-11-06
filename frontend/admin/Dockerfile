# 后台 SPA 镜像：构建出静态文件后用 nginx 托管在 /admin/。构建上下文是仓库根目录。
# 生产与公开站同域（宝塔 Nginx 把 /admin/ 反代到这里），VITE_WEB_ORIGIN 留空即可。
FROM node:22-bookworm-slim AS build

RUN corepack enable && corepack prepare pnpm@10.22.0 --activate
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY frontend/web/package.json frontend/web/
COPY frontend/admin/package.json frontend/admin/
RUN pnpm install --frozen-lockfile --filter @52tokens/admin...
COPY shared shared
COPY frontend/admin frontend/admin
RUN pnpm --filter @52tokens/admin build

FROM nginx:1.27-alpine
COPY frontend/admin/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/frontend/admin/dist /usr/share/nginx/html/admin
EXPOSE 80
