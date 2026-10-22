"""日志：统一走 loguru，并接管标准库 logging（uvicorn、sqlalchemy 等）。"""

import logging
import sys

from loguru import logger

from app.core.config import Settings


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(settings: Settings) -> None:
    logger.remove()
    if settings.is_dev:
        # dev：彩色 + 完整堆栈 + 变量值，便于排查
        logger.add(sys.stderr, level=settings.log_level, backtrace=True, diagnose=True)
    else:
        # prod：结构化 JSON，关闭 diagnose 防止变量值泄露敏感信息
        logger.add(sys.stderr, level=settings.log_level, serialize=True, diagnose=False)

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False
