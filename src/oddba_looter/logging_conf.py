from __future__ import annotations

import sys
from pathlib import Path
from loguru import logger

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "| <level>{level: <8}</level> "
    "| <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "oddba_{time:YYYY-MM}.log"


def setup_logging() -> None:
    """配置 loguru：终端彩色输出 + 文件落盘（自动轮转）"""
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format=_CONSOLE_FORMAT,
        colorize=True,
    )
    logger.add(
        _LOG_FILE,
        level="DEBUG",
        format=_FILE_FORMAT,
        rotation="1 month",
        retention=12,
        encoding="utf-8",
    )
