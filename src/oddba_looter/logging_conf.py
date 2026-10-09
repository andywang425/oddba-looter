from __future__ import annotations

import sys

from loguru import logger

from .config import LOG_DIR

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "| <level>{level: <8}</level> "
    "| <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"


def setup_logging(debug: bool = False) -> None:
    """初始化终端和文件日志"""
    logger.remove()
    level = "DEBUG" if debug else "INFO"

    logger.add(
        sys.stderr,
        level=level,
        format=_CONSOLE_FORMAT,
        diagnose=debug,
    )

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.add(
        LOG_DIR / "oddba_{time:YYYY-MM}.log",
        level=level,
        format=_FILE_FORMAT,
        diagnose=debug,
        rotation="monthly",
        retention=12,
        encoding="utf-8",
    )
