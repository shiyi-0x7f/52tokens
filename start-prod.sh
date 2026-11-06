#!/usr/bin/env bash
# 生产一键部署 / 更新：构建镜像 → 数据库迁移 → 启动（或滚动替换）所有服务。
#
# 用法（在服务器的仓库目录下）：
#   ./start-prod.sh          构建、迁移、启动
#   ./start-prod.sh --seed   另外导入 data/seed/ 种子（首次部署或种子有更新时）
#
# 前提：已按 dev_docs/devops/deployment.md 准备好 .env.prod、宝塔 PostgreSQL / Redis 与 Nginx。
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=".env.prod"
[ -f "$ENV_FILE" ] || { echo "缺少 $ENV_FILE，请先从 .env.prod.example 复制并填写"; exit 1; }

COMPOSE=(docker compose -f compose.yaml -f compose.prod.yaml --env-file "$ENV_FILE")

echo "==> 构建镜像"
"${COMPOSE[@]}" build

echo "==> 数据库迁移"
"${COMPOSE[@]}" run --rm --no-deps api alembic upgrade head

if [ "${1:-}" = "--seed" ]; then
  echo "==> 导入种子数据"
  "${COMPOSE[@]}" run --rm --no-deps api python -m app.cli.seed
fi

echo "==> 启动服务"
"${COMPOSE[@]}" up -d --remove-orphans

echo "==> 当前状态（健康检查每 30 秒一次，刚启动时可能显示 starting）"
"${COMPOSE[@]}" ps
