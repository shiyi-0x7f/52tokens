# 后端镜像：API（uvicorn）和采集 worker（arq）共用，用 compose 的 command 区分。
# 构建上下文是仓库根目录：后端按仓库结构读取 shared/（错误码表）和 data/（种子、App Store 配置）。
FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.7.8 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    APP_ENV=prod

WORKDIR /srv/backend

# 先只装依赖，代码改动时可复用这一层缓存
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY shared /srv/shared
COPY data /srv/data
COPY backend /srv/backend
RUN uv sync --frozen --no-dev

ENV PATH="/srv/backend/.venv/bin:$PATH"

# 非 root 运行
RUN useradd --system --uid 10001 app && chown -R app /srv
USER app

EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--proxy-headers", "--forwarded-allow-ips", "*"]
