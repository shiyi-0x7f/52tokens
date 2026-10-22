#!/usr/bin/env bash
# 一键启动开发环境：后端 API + 公开站（Astro）+ 后台（Vite）。Windows 用 Git Bash 运行。
# 启动前先停掉本项目上一次残留的开发进程，避免「已有开发服务在运行」和端口漂移。
# 端口固定 + 自动避让：.env.dev 里的端口被其他程序占用时自动 +1，并把实际端口回写 .env.dev。
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

# 停掉本项目上一次残留的开发进程（终端被直接关掉时退出清理来不及执行）。
# Windows 上 venv 的 python.exe 只是启动器，真正的解释器和 uvicorn 热重载的工作进程是它的子进程，
# 命令行里不含项目路径，所以：
#   1. 命令行含本项目路径的 uvicorn / astro / vite 进程 → taskkill /T 连同子进程树一起结束；
#   2. 兜底：本项目端口仍被占用且登记的占用者已死 → 按 parent_pid=<占用者> 找到孤儿工作进程结束。
stop_previous() {
  local ports="$*"
  if command -v powershell.exe >/dev/null 2>&1; then
    local root
    root="$(pwd -W 2>/dev/null || pwd)"
    powershell.exe -NoProfile -NonInteractive -Command "
      \$root = '${root}'.Replace('/', '\\');
      \$all = Get-CimInstance Win32_Process;
      \$all | Where-Object { \$_.CommandLine -and \$_.CommandLine.Contains(\$root) -and
                             \$_.CommandLine -match 'uvicorn|astro|vite' } |
        ForEach-Object {
          taskkill /F /T /PID \$_.ProcessId 2>\$null | Out-Null;
          Write-Output ('已停止上一次残留的开发进程 pid=' + \$_.ProcessId)
        };
      Start-Sleep -Milliseconds 500;
      foreach (\$port in '${ports}'.Split(' ', [StringSplitOptions]::RemoveEmptyEntries)) {
        \$conn = Get-NetTCPConnection -State Listen -LocalPort \$port -ErrorAction SilentlyContinue | Select-Object -First 1;
        if (-not \$conn -or (Get-Process -Id \$conn.OwningProcess -ErrorAction SilentlyContinue)) { continue }
        \$all | Where-Object { \$_.CommandLine -match ('parent_pid=' + \$conn.OwningProcess + '\b') } |
          ForEach-Object {
            Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue;
            Write-Output ('已停止占用端口 ' + \$port + ' 的孤儿进程 pid=' + \$_.ProcessId)
          }
      }"
  else
    pkill -f "$(pwd)/.*(uvicorn|astro|vite)" 2>/dev/null && echo "已停止上一次残留的开发进程" || true
  fi
  sleep 1
}

# 带 ./ 前缀：POSIX 模式下不带路径的 source 只查 PATH，不查当前目录
set -a; source "./$ENV_FILE"; set +a

stop_previous "${API_PORT:-8100}" "${WEB_PORT:-4321}" "${ADMIN_PORT:-5174}"

CONFIGURED_WEB_PORT="${WEB_PORT:-4321}"
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

# Google 回调地址里写死了公开站端口，端口避让后 Google 登录会失败，必须提醒
if [ "$WEB_PORT" != "$CONFIGURED_WEB_PORT" ] && [ -n "${GOOGLE_REDIRECT_URI:-}" ]; then
  echo "⚠ 公开站端口 ${CONFIGURED_WEB_PORT} 被其他程序占用，已改用 ${WEB_PORT}。"
  echo "  GOOGLE_REDIRECT_URI 仍是 ${GOOGLE_REDIRECT_URI}，Google 登录会因回调地址不匹配而失败；"
  echo "  请释放 ${CONFIGURED_WEB_PORT} 端口后重启，并把 .env.dev 里的 WEB_PORT 改回 ${CONFIGURED_WEB_PORT}。"
fi

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
