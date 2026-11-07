#!/usr/bin/env bash
# 本机构建三个生产镜像并推到阿里云 ACR；服务器上只拉取（start-prod.sh）。
#
# 用法（仓库根目录，Git Bash / Linux / macOS）：
#   deploy/build-push.sh            打两个标签：当前提交的短哈希 + latest
#   deploy/build-push.sh v1.2.0     额外打一个指定标签
#
# 前提：已 docker login 到 ACR（docker login crpi-bveintih61x5c20a.cn-hangzhou.personal.cr.aliyuncs.com）。
# 可用环境变量覆盖：IMAGE_REGISTRY、SITE_URL。
set -euo pipefail
cd "$(dirname "$0")/.."

REGISTRY="${IMAGE_REGISTRY:-crpi-bveintih61x5c20a.cn-hangzhou.personal.cr.aliyuncs.com/shiyi_acr}"
# 公开站镜像唯一写死的值：canonical / sitemap / 分享图的绝对地址
SITE_URL="${SITE_URL:-https://52tokens.cc}"
SHA="$(git rev-parse --short HEAD)"
EXTRA_TAG="${1:-}"

if [ -n "$(git status --porcelain)" ]; then
  echo "警告：工作区有未提交的改动，镜像会包含这些改动，但标签仍是 $SHA" >&2
fi

# 服务器是 x86_64 Linux；在 Apple Silicon 等机器上构建也要产出 amd64 镜像
PLATFORM="linux/amd64"

build() {
  local name="$1" dockerfile="$2"
  shift 2
  local tags=(-t "$REGISTRY/$name:$SHA" -t "$REGISTRY/$name:latest")
  [ -n "$EXTRA_TAG" ] && tags+=(-t "$REGISTRY/$name:$EXTRA_TAG")
  echo "==> 构建 $name"
  docker build --platform "$PLATFORM" -f "$dockerfile" "${tags[@]}" "$@" .
}

build 52tokens-backend backend/Dockerfile
build 52tokens-frontend frontend/web/Dockerfile --build-arg "SITE_URL=$SITE_URL"
build 52tokens-admin frontend/admin/Dockerfile

for name in 52tokens-backend 52tokens-frontend 52tokens-admin; do
  for tag in "$SHA" latest $EXTRA_TAG; do
    echo "==> 推送 $name:$tag"
    docker push "$REGISTRY/$name:$tag"
  done
done

echo
echo "完成：标签 $SHA${EXTRA_TAG:+、$EXTRA_TAG}、latest"
echo "服务器上执行 ./start-prod.sh（.env.prod 里 IMAGE_TAG 留空即用 latest，要固定版本就填 $SHA）"
