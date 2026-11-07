# 后台 SPA 镜像：构建出静态文件后用 nginx 托管。构建上下文是仓库根目录。
# 后台路径不写进镜像：构建时用占位路径 /__ADMIN_BASE__/，容器启动时按环境变量 ADMIN_BASE_PATH
# 替换（docker-entrypoint.sh），nginx 配置也由模板按它生成。生产与公开站同域，VITE_WEB_ORIGIN 留空。
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
COPY frontend/admin/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY frontend/admin/docker-entrypoint.sh /docker-entrypoint.d/40-admin-base-path.sh
RUN chmod +x /docker-entrypoint.d/40-admin-base-path.sh && rm -f /etc/nginx/conf.d/default.conf
COPY --from=build /repo/frontend/admin/dist /opt/admin-dist
EXPOSE 80
