#!/bin/sh
# 后台容器启动时：把构建产物放到 ADMIN_BASE_PATH 下，并把占位路径 /__ADMIN_BASE__/ 换成真实路径。
# 真实路径只在服务器的 .env.prod 里（仓库公开，不能写进代码或镜像）。
# 由 nginx 镜像的 /docker-entrypoint.sh 在启动 nginx 前自动执行（/docker-entrypoint.d/*.sh）。
set -eu

path="${ADMIN_BASE_PATH:-}"
if ! printf '%s' "$path" | grep -Eq '^/[A-Za-z0-9_-]{6,64}/$'; then
  echo "ADMIN_BASE_PATH 必须形如 /随机字符串/（6-64 位字母、数字、- 或 _），当前：'$path'" >&2
  exit 1
fi

html=/usr/share/nginx/html
dest="$html${path%/}"
# 每次启动都从原始产物重新生成，换路径时旧目录不会残留
find "$html" -mindepth 1 -delete
mkdir -p "$dest"
cp -R /opt/admin-dist/. "$dest/"
# 两种写法都要换：原样的 /__ADMIN_BASE__/，以及构建时被压缩器预先 URL 编码的 %2F__ADMIN_BASE__%2F
# （如登录跳转的 next 参数）。路径只含字母、数字、- 和 _，编码后只有两端的斜杠变成 %2F
inner="${path#/}"
inner="${inner%/}"
find "$dest" -type f \( -name '*.html' -o -name '*.js' -o -name '*.css' \) \
  -exec sed -i -e "s#/__ADMIN_BASE__/#$path#g" -e "s#%2F__ADMIN_BASE__%2F#%2F$inner%2F#g" {} +
# 还有残留说明出现了新的写法，宁可启动失败也不要带着占位路径上线
if grep -rq "__ADMIN_BASE__" "$dest"; then
  echo "后台产物里仍有未替换的占位路径 __ADMIN_BASE__" >&2
  exit 1
fi
