from __future__ import annotations

from html import unescape

from loguru import logger

from .client import ODDBAClient
from .parser import parse_claimable_tasks, parse_claimable_treasures, parse_sign_status


def run_sign(client: ODDBAClient, sign_page_html: str) -> bool:
    logger.info("[每日签到] 开始")
    if parse_sign_status(sign_page_html):
        logger.warning("[每日签到] 今日已签到，跳过")
        return False
    result = client.do_sign()
    if result.get("code") == 1:
        logger.success(f"[每日签到] 签到成功，累计签到 {result.get('sign_c', '?')} 天")
        return True
    else:
        logger.error(f"[每日签到] 签到失败：{unescape(result.get('msg', ''))}")
        return False


def run_treasure(client: ODDBAClient, sign_page_html: str, do_sign: bool) -> None:
    logger.info("[领取签到宝箱奖励] 开始")
    treasures = parse_claimable_treasures(sign_page_html, do_sign)
    if not treasures:
        logger.warning("[领取签到宝箱奖励] 暂无可领取的宝箱奖励")
        return
    for number in treasures:
        result = client.claim_treasure(number)
        if result.get("code") == 1:
            logger.success(f"[领取签到宝箱奖励] 宝箱 {number} 领取成功")
        else:
            logger.error(
                f"[领取签到宝箱奖励] 宝箱 {number} 领取失败：{unescape(result.get('msg', ''))}")


def run_task(client: ODDBAClient) -> None:
    logger.info("[领取每日任务奖励] 开始")
    html = client.get_task_page()
    tasks = parse_claimable_tasks(html)
    if not tasks:
        logger.warning("[领取每日任务奖励] 暂无可领取的任务奖励")
        return
    for task_id in tasks:
        result = client.claim_task(task_id)
        if result.get("code") == 1:
            logger.success(f"[领取每日任务奖励] 任务 {task_id} 领取成功")
        else:
            logger.error(
                f"[领取每日任务奖励] 任务 {task_id} 领取失败：{unescape(result.get('msg', ''))}")
