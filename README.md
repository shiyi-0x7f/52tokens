# 52tokens

AI 羊毛热榜与价格雷达：官方 API / 模型价、免费额度与签到活动、官方订阅地区价、卡网比价。
规划见 [dev_docs/planning/roadmap.md](dev_docs/planning/roadmap.md)。

## 技术栈

| 部分                  | 技术                                                                                                    |
| --------------------- | ------------------------------------------------------------------------------------------------------- |
| 公开站 `frontend/web` | Astro 7（SSR，Node adapter）+ Tailwind v4 + React（默认只做服务端渲染）+ pino                           |
| 后台 `frontend/admin` | React + Vite + Tailwind v4                                                                              |
| 后端 `backend`        | FastAPI + SQLAlchemy 2（async）+ Alembic + arq（采集 worker）+ loguru                                   |
| 存储                  | PostgreSQL 16 + Redis 7                                                                                 |
| 身份                  | SCC 统一身份（见 [dev_docs/refs/software_control_center.md](dev_docs/refs/software_control_center.md)） |
| 工具链                | uv（Python）、pnpm（JS/TS）                                                                             |

架构约束：公开站服务端是公开数据的唯一出口，后端公开数据接口 `/internal/v1/*` 只接受带内部令牌的内网调用，浏览器拿到的只有 HTML。详见 [dev_docs/architecture/data-protection.md](dev_docs/architecture/data-protection.md)。

## 本地启动

前置：Node ≥ 22.12、pnpm、uv、Git Bash；本机 Docker 里有 `dev-postgres` 和 `dev-redis`。

```bash
cp .env.dev.example .env.dev     # 填数据库密码、内部令牌等
pnpm install
(cd backend && uv sync)
bash start-dev.sh                # 端口被占用会自动 +1 并回写 .env.dev
```

- 后端 API 文档：`http://127.0.0.1:8100/docs`（仅 dev）
- 公开站：`http://127.0.0.1:4321/`
- 后台：`http://127.0.0.1:5174/admin/`
- 采集 worker：`cd backend && uv run arq app.workers.settings.WorkerSettings`

数据库首次使用需要在 `dev-postgres` 里建项目专属库和账号（库名、账号均为 `tokens52`），迁移由 `start-dev.sh` 自动执行。

## 测试与质量门禁

```bash
bash scripts/check.sh            # 或 just check：格式化检查 → lint → 类型检查 → 测试
```

本地、pre-commit（`uv tool install pre-commit && pre-commit install`）和 CI 跑的是同一个脚本。

- 后端测试：`backend/tests/`（pytest）
- 前端测试：`frontend/web/test/`（vitest）

## 目录

```
backend/            FastAPI 后端（api/ core/ db/ collectors/ workers/）
frontend/web/       公开站（Astro）
frontend/admin/     后台（Vite SPA）
shared/             前后端共用资源（业务码表 error-codes.json）
dev_docs/           规划、架构、调研、设计稿、对接文档
scripts/            门禁等脚本
```
