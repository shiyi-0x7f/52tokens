#!/usr/bin/env bash
# 一键启动开发环境：后端 API + 公开站（Astro）+ 后台（Vite）。Windows 用 Git Bash 运行。
# 端口固定 + 自动避让：.env.dev 里的端口被占用时自动 +1，并把实际端口回写 .env.dev。
# worker 按需另开：cd backend && uv run arq app.workers.settings.WorkerSettings
# 用 sh 调用时切回 bash（下面用到 /dev/tcp 等 bash 特性）
if [ -z "${BASH_VERSION:-}" ] || shopt -qo posix; then exec bash "$0" "$@"; fi
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=".env.dev"
[ -f "$ENV_FILE" ] || { echo "缺少 $ENV_FILE，请先从 .env.dev.example 复制"; exit 1; }

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && { exec 3>&- 3<&-; return 0; } || return 1
}

find_free_port() {
  local port="$1" tried=0
  while port_in_use "$port"; do
    port=$((port + 1)); tried=$((tried + 1))
    [ "$tried" -ge 100 ] && { echo "找不到空闲端口（起点 $1）" >&2; exit 1; }
  done
  echo "$port"
}

# 把 KEY=旧值 改成 KEY=新值（只改这一行）
write_back() {
  local key="$1" value="$2"
  sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
}

# 带 ./ 前缀：POSIX 模式下不带路径的 source 只查 PATH，不查当前目录
set -a; source "./$ENV_FILE"; set +a

API_PORT="$(find_free_port "${API_PORT:-8100}")"
WEB_PORT="$(find_free_port "${WEB_PORT:-4321}")"
ADMIN_PORT="$(find_free_port "${ADMIN_PORT:-5174}")"
API_INTERNAL_URL="http://127.0.0.1:${API_PORT}"

write_back API_PORT "$API_PORT"
write_back WEB_PORT "$WEB_PORT"
write_back ADMIN_PORT "$ADMIN_PORT"
write_back API_INTERNAL_URL "$API_INTERNAL_URL"
export API_PORT WEB_PORT ADMIN_PORT API_INTERNAL_URL

echo "后端 API:   http://127.0.0.1:${API_PORT}/docs"
echo "公开站:     http://127.0.0.1:${WEB_PORT}/"
echo "后台:       http://127.0.0.1:${ADMIN_PORT}/admin/"

PIDS=()

# 退出时结束所有子进程。Git Bash 下 kill 杀不到 pnpm/uv 拉起的原生 Windows 进程，
# 所以 Windows 上按 winpid 用 taskkill /T 结束整棵进程树
cleanup() {
  trap - EXIT INT TERM
  local pid
  for pid in "${PIDS[@]}"; do
    if [ -r "/proc/$pid/winpid" ]; then
      taskkill //F //T //PID "$(cat "/proc/$pid/winpid")" >/dev/null 2>&1 || true
    fi
  done
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd backend && uv run alembic upgrade head && \
  uv run uvicorn app.main:app --reload --host 127.0.0.1 --port "$API_PORT") &
PIDS+=("$!")
pnpm --filter @52tokens/web dev &
PIDS+=("$!")
pnpm --filter @52tokens/admin dev &
PIDS+=("$!")
wait
