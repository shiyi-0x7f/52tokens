#!/usr/bin/env bash
# 质量门禁：格式化检查 → lint → 类型检查 → 测试。本地、pre-commit 和 CI 跑的都是这一个脚本。
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n==> %s\n' "$1"; }

step "格式化检查"
(cd backend && uv run ruff format --check .)
pnpm exec prettier --check .

step "Lint"
(cd backend && uv run ruff check .)
pnpm exec eslint .

step "类型检查"
(cd backend && uv run mypy)
# astro check 只做类型检查，不需要真实令牌
INTERNAL_API_TOKEN="${INTERNAL_API_TOKEN:-typecheck-only}" pnpm -r typecheck

step "测试"
(cd backend && uv run pytest -q)
pnpm -r --if-present test

printf '\n全部通过\n'
