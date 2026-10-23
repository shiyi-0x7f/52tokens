"""进程入口必须注册全部 ORM 模型，否则写库时外键（如 deals.reviewed_by_id → users）解析失败。

conftest 会导入全部模型，测试里暴露不出来，所以在干净的子进程里检查各入口。
"""

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
EXPECTED = {"users", "platforms", "deals", "deal_sources", "outbound_clicks"}


@pytest.mark.parametrize("module", ["app.workers.settings", "app.cli.collect", "app.main"])
def test_entrypoint_registers_all_tables(module: str) -> None:
    code = (
        f"import {module}\n"
        "from app.db.base import Base\n"
        "print(','.join(sorted(Base.metadata.tables)))\n"
    )
    out = subprocess.run(  # noqa: S603  固定的解释器和代码
        [sys.executable, "-c", code],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
        env={"APP_ENV": "test", "INTERNAL_API_TOKEN": "x", "SYSTEMROOT": "C:\\Windows"}
        if sys.platform == "win32"
        else {"APP_ENV": "test", "INTERNAL_API_TOKEN": "x"},
    )
    tables = set(out.stdout.strip().split(","))
    assert EXPECTED <= tables, f"{module} 缺少：{EXPECTED - tables}"
