#!/usr/bin/env bash
# 服务器一键部署 / 更新：从阿里云 ACR 拉取镜像 → 数据库迁移 → 启动（或替换）所有服务。不在服务器上构建。
# 镜像由本机 deploy/build-push.sh 构建并推送。
#
# 用法（在服务器的仓库目录下）：
#   ./start-prod.sh          拉取、迁移、启动
#   ./start-prod.sh --seed   另外导入 data/seed/ 种子（首次部署或种子有更新时；种子在镜像里）
#
# 前提：已 docker login 到 ACR；已按 dev_docs/devops/deployment.md 准备好 .env.prod、
# 宝塔 PostgreSQL / Redis 与 Nginx。
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=".env.prod"
[ -f "$ENV_FILE" ] || { echo "缺少 $ENV_FILE，请先从 .env.prod.example 复制并填写"; exit 1; }

# 随机十六进制串；没有 openssl 时退回 /dev/urandom
rand_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

# 读取 .env.prod 里某个键的值（不存在时为空）
env_value() {
  grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true
}

# 键为空或仍是示例占位值（含 <）时，生成随机值写回 .env.prod；已有值不动，重启后保持不变
GENERATED=()
ensure_random() {
  local key="$1" value="$2" current
  current="$(env_value "$key")"
  if [ -n "$current" ] && [[ "$current" != *"<"* ]]; then
    return
  fi
  if grep -qE "^$key=" "$ENV_FILE"; then
    sed -i "s|^$key=.*|$key=$value|" "$ENV_FILE"
  else
    printf '\n%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
  GENERATED+=("$key")
}

ensure_random INTERNAL_API_TOKEN "$(rand_hex 32)"
ensure_random ADMIN_BASE_PATH "/$(rand_hex 6)/"
if [ "${#GENERATED[@]}" -gt 0 ]; then
  echo "==> 已生成并写入 $ENV_FILE：${GENERATED[*]}"
fi

COMPOSE=(docker compose -f compose.yaml -f compose.prod.yaml --env-file "$ENV_FILE")

echo "==> 拉取镜像"
"${COMPOSE[@]}" pull

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

ADMIN_PATH="$(env_value ADMIN_BASE_PATH)"
echo
echo "后台地址：$(env_value SITE_URL)$ADMIN_PATH"
if [[ " ${GENERATED[*]} " == *" ADMIN_BASE_PATH "* ]]; then
  echo "注意：后台路径是新生成的，宝塔 Nginx 里后台那条 location 要改成 ^~ $ADMIN_PATH ，然后 nginx -t && nginx -s reload"
fi
