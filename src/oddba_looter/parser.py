from __future__ import annotations

import re

from bs4 import BeautifulSoup

_TREASURE_ACTION_RE = re.compile(r"jinsom_sign_treasure\((\d+)")
_TASK_FINISH_RE = re.compile(r'jinsom_task_finish\(\s*"([^"]+)"')
_NUMBER_RE = re.compile(r"\d+")


def parse_login_status(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one(".jinsom-header .jinsom-header-menu-avatar"))


def parse_sign_status(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one(".jinsom-sign-page-btn.had"))


def parse_claimable_treasures(html: str, do_sign: bool) -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    month_sign_box = soup.select_one(".jinsom-sign-page-box.month")
    if month_sign_box is None:
        return []
    month_sign_days_span = month_sign_box.select_one(
        ".jinsom-sign-page-month-days span")
    if month_sign_days_span is None:
        return []
    month_sign_days = int(month_sign_days_span.get_text())
    if do_sign:
        month_sign_days += 1

    claimable: list[int] = []
    for month_sign_item in month_sign_box.select(".content > li"):
        btn = month_sign_item.select_one(".btn")
        if btn is None:
            continue
        if "had" in (btn.get("class") or []):
            continue
        onclick = btn.get("onclick")
        if not isinstance(onclick, str):
            continue
        required_sign_days_span = month_sign_item.select_one(".img span")
        if required_sign_days_span is None:
            continue
        required_sign_days_match = _NUMBER_RE.search(
            required_sign_days_span.get_text())
        if required_sign_days_match is None:
            continue
        required_sign_days = int(required_sign_days_match.group())
        if month_sign_days < required_sign_days:
            continue
        m = _TREASURE_ACTION_RE.search(onclick)
        if m:
            claimable.append(int(m.group(1)))
    return claimable


def parse_claimable_tasks(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    daily_task_content = soup.select_one(
        ".jinsom-task-form-content .content .on")
    if daily_task_content is None:
        return []

    claimable: list[str] = []
    for status in daily_task_content.select(".status.on"):
        onclick = status.get("onclick")
        if not isinstance(onclick, str):
            continue
        m = _TASK_FINISH_RE.search(onclick)
        if m:
            claimable.append(m.group(1))
    return claimable
