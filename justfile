# 统一入口（需安装 just：uv tool install rust-just）。不装 just 时直接运行 bash scripts/*.sh

default:
    @just --list

# 质量门禁：格式化检查 → lint → 类型检查 → 测试（CI 跑同一套）
check:
    bash scripts/check.sh

# 一键格式化（会改文件）
fmt:
    cd backend && uv run ruff format . && uv run ruff check --fix .
    pnpm exec prettier --write . && pnpm exec eslint --fix .

# 启动开发环境
dev:
    bash start-dev.sh

# 生成数据库迁移：just migration "add deals table"
migration message:
    cd backend && uv run alembic revision --autogenerate -m "{{message}}"
