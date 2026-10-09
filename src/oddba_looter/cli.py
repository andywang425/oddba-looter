from __future__ import annotations

import sys

from loguru import logger

from .client import ODDBAClient, RateLimitError
from .config import ConfigError, load_settings
from .logging_conf import setup_logging
from .tasks import run_sign, run_task, run_treasure


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"配置错误：{e}", file=sys.stderr)
        return 2

    try:
        setup_logging(debug=settings.debug)
    except OSError as e:
        print(f"日志初始化失败：{e}", file=sys.stderr)
        return 2

    try:
        with ODDBAClient(settings) as client:
            client.authenticate()
            state, did_sign, failures = run_sign(client)
            if state:
                failures += run_treasure(client, state, did_sign)
            failures += run_task(client)

        if failures:
            logger.error("执行结束，共 {} 项任务失败", failures)
            return 1

        logger.success("执行完成")
        return 0
    except RateLimitError as e:
        logger.error("{}", e)
        return 2
    except KeyboardInterrupt:
        logger.warning("用户中断执行")
        return 2
    except Exception as e:
        logger.exception("执行时发生未预期错误：{}", e)
        return 2
