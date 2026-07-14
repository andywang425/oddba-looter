from __future__ import annotations

import os

from dotenv import load_dotenv
from loguru import logger

from .client import ODDBAClient
from .logging_conf import setup_logging
from .parser import parse_login_status
from .tasks import run_sign, run_task, run_treasure


@logger.catch(level="CRITICAL", reraise=True)
def main() -> None:
    setup_logging()
    load_dotenv()
    cookie = os.environ.get("ODDBA_COOKIE", "").strip()
    debug = os.environ.get("ODDBA_LOOTER_DEBUG", "").strip() in (
        "1", "true", "True", "yes", "Yes", "on", "On")

    client = ODDBAClient(cookie, debug=debug)

    # 拿到签到中心页面 HTML 的同时获取短期会话 Cookie（server_name_session）
    logger.info("正在访问签到中心页面...")
    sign_page_html = client.get_sign_page()

    if not parse_login_status(sign_page_html):
        logger.error("未检测到登录状态，请检查 ODDBA_COOKIE 是否有效或已过期")
        return

    do_sign = run_sign(client, sign_page_html)
    run_treasure(client, sign_page_html, do_sign)
    run_task(client)

    logger.success("完成")
