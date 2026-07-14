from __future__ import annotations

import sys

from curl_cffi import requests
from loguru import logger

from .config import (
    BASE_URL,
    IMPERSONATE,
    SIGN_ACTION,
    SIGN_PAGE,
    SIGN_TREASURE_ACTION,
    TASK_ACTION,
    TASK_PAGE,
)


class ODDBAClient:

    def __init__(self, cookie: str, *, debug: bool = False) -> None:
        if not cookie:
            logger.error(
                "未配置 ODDBA_COOKIE，请复制 .env.example 为 .env 并填入登录 Cookie")
            sys.exit(2)

        self.session = requests.Session(
            impersonate=IMPERSONATE, retry=2, timeout=60, raise_for_status=True, debug=debug)

        for pair in cookie.split(";"):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            name, _, value = pair.partition("=")
            self.session.cookies.set(name.strip(), value.strip())

    def get_sign_page(self) -> str:
        return self.session.get(SIGN_PAGE).text

    def do_sign(self) -> dict:
        return self.session.post(
            SIGN_ACTION,
            data={"sign": "1", "ticket": "", "randstr": ""},
            headers={"Referer": SIGN_PAGE, "Origin": BASE_URL}
        ).json()

    def claim_treasure(self, number: int) -> dict:
        return self.session.post(
            SIGN_TREASURE_ACTION,
            data={"number": str(number)},
            headers={"Referer": SIGN_PAGE, "Origin": BASE_URL}
        ).json()

    def get_task_page(self) -> str:
        return self.session.get(
            TASK_PAGE,
            headers={"Referer": SIGN_PAGE, "Origin": BASE_URL}
        ).text

    def claim_task(self, task_id: str) -> dict:
        return self.session.post(
            TASK_ACTION,
            data={"task_id": task_id, "type": "day"},
            headers={"Referer": SIGN_PAGE, "Origin": BASE_URL}
        ).json()
