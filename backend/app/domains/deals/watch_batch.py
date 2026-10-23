"""批量检查全部监测来源：同一时间只跑一批（Redis 锁），记录进度和上一批的汇总。

后台「全部检查」和 worker 定时检查共用这把锁，手动和定时不会同时跑。
"""

from datetime import UTC, datetime

from pydantic import BaseModel

from app.core.kv import KeyValueStore
from app.domains.deals.watch import DealWatchService

RUNNING_KEY = "deal_watch:running"
LAST_KEY = "deal_watch:last"
# 锁的兜底过期时间：进程中途挂掉时不至于永远锁住
RUNNING_TTL_SECONDS = 60 * 60
LAST_TTL_SECONDS = 30 * 24 * 3600


class BatchProgress(BaseModel):
    started_at: datetime
    total: int = 0
    done: int = 0


class BatchSummary(BaseModel):
    started_at: datetime
    finished_at: datetime
    checked: int
    created: int
    reconfirmed: int
    failed: int


class BatchStatus(BaseModel):
    running: BatchProgress | None
    last: BatchSummary | None


class BatchCheckService:
    def __init__(self, store: KeyValueStore) -> None:
        self.store = store

    async def status(self) -> BatchStatus:
        running = await self.store.get(RUNNING_KEY)
        last = await self.store.get(LAST_KEY)
        return BatchStatus(
            running=BatchProgress.model_validate_json(running) if running else None,
            last=BatchSummary.model_validate_json(last) if last else None,
        )

    async def acquire(self) -> bool:
        """抢锁；已有一批在跑时返回 False。"""
        progress = BatchProgress(started_at=datetime.now(UTC))
        return await self.store.set_if_absent(
            RUNNING_KEY, progress.model_dump_json(), RUNNING_TTL_SECONDS
        )

    async def run(self, watch: DealWatchService) -> BatchSummary:
        """必须先 acquire 成功；无论成功失败都会释放锁。"""
        started_at = datetime.now(UTC)

        async def on_progress(done: int, total: int) -> None:
            progress = BatchProgress(started_at=started_at, total=total, done=done)
            await self.store.set(RUNNING_KEY, progress.model_dump_json(), RUNNING_TTL_SECONDS)

        try:
            reports = await watch.check_all(on_progress)
            summary = BatchSummary(
                started_at=started_at,
                finished_at=datetime.now(UTC),
                checked=len(reports),
                created=sum(r.created for r in reports),
                reconfirmed=sum(r.reconfirmed for r in reports),
                failed=sum(r.status == "failed" for r in reports),
            )
            await self.store.set(LAST_KEY, summary.model_dump_json(), LAST_TTL_SECONDS)
            return summary
        finally:
            await self.store.delete(RUNNING_KEY)
