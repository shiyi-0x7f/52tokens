# 公开站镜像（Astro SSR，Node standalone）。构建上下文是仓库根目录（pnpm workspace）。
#
# 注意：@resvg/resvg-js 是原生模块，必须在目标系统（这里是镜像里的 Linux）上 pnpm install，
# 不能拷贝开发机的 node_modules。
# SITE_URL 和 Astro 的公开变量（TURNSTILE_SITE_KEY 等）在构建时写进产物，所以作为构建参数传入；
# 密钥类变量（INTERNAL_API_TOKEN、REDIS_URL 等）运行时由 env_file 注入。
FROM node:22-bookworm-slim

RUN corepack enable && corepack prepare pnpm@10.22.0 --activate

WORKDIR /repo

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY frontend/web/package.json frontend/web/
COPY frontend/admin/package.json frontend/admin/
RUN pnpm install --frozen-lockfile --filter @52tokens/web...

COPY shared shared
COPY frontend/web frontend/web

ARG SITE_URL
ARG TURNSTILE_SITE_KEY
ARG WECHAT_CALLBACK_ORIGIN
ARG REDIS_KEY_PREFIX
ARG TRUSTED_IP_HEADER
ARG RATE_LIMIT_PER_MINUTE=120
RUN test -n "$SITE_URL" || (echo "构建参数 SITE_URL 不能为空" && exit 1)
RUN pnpm --filter @52tokens/web build

WORKDIR /repo/frontend/web
# 以 node 用户运行；Astro 的文件会话存储会写 node_modules/.astro，需要可写
RUN chown -R node:node /repo/frontend/web
ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=4321

USER node
EXPOSE 4321
CMD ["node", "dist/server/entry.mjs"]
