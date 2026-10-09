from __future__ import annotations

from collections.abc import Callable

from loguru import logger

from .client import (
    JsonObject,
    ODDBAClient,
    ODDBAError,
    RateLimitError,
    ResponseError,
    UncertainResultError,
    require_field,
)


def _reward_amount(reward: JsonObject) -> int | float | str | None:
    """读取奖励数量，服务端可能回传数字或数字字符串，缺失或类型异常时返回 None"""
    amount = reward.get("amount")
    if amount is None or isinstance(amount, bool):
        return None
    return amount if isinstance(amount, int | float | str) else None


FIXED_REWARD_NAMES = {"vip_days": "VIP 会员", "invite_code": "邀请码"}


def _reward_text(value: object) -> str:
    """取一个能直接拼进日志的文本，缺失或非字符串时返回空串"""
    return value.strip() if isinstance(value, str) else ""


def _reward_title(reward: JsonObject, kind: str) -> str:
    """奖励叫什么：固定档用站点叫法，头衔用它本身那段文字，其余用服务端给的 name"""
    if kind == "user_title":
        title = _reward_text(reward.get("title"))
        if not title:
            logger.warning("头衔奖励未提供 title：{}", reward)
            title = "未知"
        return f"头衔「{title}」"

    name = _reward_text(reward.get("name")) or FIXED_REWARD_NAMES.get(kind, "")
    if not name:
        return f"未知奖励（{kind}）"
    return name


def _reward_quantity(reward: JsonObject, kind: str) -> str:
    """奖励的数量那一截，永久会员不依赖数量，其余缺数量的档返回空串"""
    if kind == "vip_days" and reward.get("forever"):
        return "永久"

    amount = _reward_amount(reward)
    if kind == "user_title" or amount is None:
        return ""

    if kind == "currency":
        return f"+{amount}"
    if kind == "vip_days":
        return f"+{amount} 天"
    return f"×{amount}"  # 道具、邀请码，以及本站还没用上的类型都按"数量"处理


def _reward_note(reward: JsonObject, kind: str) -> str:
    """括号里那句补充说明，没有可说的就返回空串"""
    if kind == "currency":
        # 货币回传发放后的余额
        balance = reward.get("balance")
        return "" if balance is None else f"现有 {balance}"

    if kind == "prop":
        # 道具没有余额，回传发放后的剩余数量
        left = reward.get("left")
        return "" if left is None else f"剩余 {left}"

    if kind == "vip_days":
        if reward.get("forever"):
            return "不再过期"
        until = _reward_text(reward.get("until"))
        return f"有效期至 {until}" if until else ""

    if kind == "invite_code":
        codes = reward.get("codes")
        return ", ".join(str(code) for code in codes) if isinstance(codes, list) else ""

    return ""


def _reward_detail(reward: JsonObject) -> str:
    """解析奖励条目，返回奖励详情文本"""
    kind = require_field(reward, "type", str)
    # 名字与数量都可能为空，按空串跳过，避免拼出多余空格
    parts = [part for part in (_reward_title(reward, kind), _reward_quantity(reward, kind)) if part]
    # 补充说明单独一段，不与名字数量混在一行
    note = _reward_note(reward, kind)
    detail = " ".join(parts)
    return f"{detail}（{note}）" if note else detail


def _show_rewards(data: JsonObject, key: str, label: str, success_log: str) -> None:
    """解析并打印奖励；单条明细解析失败只影响该条，不会丢弃整批"""
    try:
        rewards = require_field(data, key, list)
    except ResponseError as e:
        logger.warning("{} 奖励解析失败：{}", label, e)
        return

    details: list[str] = []
    failures: list[ResponseError] = []
    for reward in rewards:
        if not isinstance(reward, dict):
            failures.append(ResponseError("奖励条目不是对象"))
            continue
        try:
            details.append(_reward_detail(reward))
        except ResponseError as e:
            failures.append(e)

    if details:
        logger.success("{} {}，获得奖励：{}", label, success_log, "，".join(details))
    if failures:
        logger.warning("{} 有 {} 条奖励明细未能解析：{}", label, len(failures), failures)
    if not details and not failures:
        logger.info("{} 服务端返回的奖励为空", label)


def run_sign(client: ODDBAClient) -> tuple[JsonObject, bool, int]:
    """执行每日签到

    Returns:
        签到中心状态、是否需要按本次签到推算宝箱解锁、失败任务数量（`0`/`1`）。
        若已刷新状态，则不再推算解锁。
    """
    logger.info("[每日签到] 开始")
    try:
        state = client.get_sign_state()
        signed = require_field(require_field(state, "user", dict), "signed", bool)
    except RateLimitError:
        raise
    except ODDBAError as e:
        logger.error("[每日签到] 获取签到中心状态失败，跳过签到和累签宝箱领取：{}", e)
        return {}, False, 1

    if signed:
        logger.info("[每日签到] 今日已签到，跳过")
        return state, False, 0

    try:
        data = client.do_sign()
    except RateLimitError:
        raise
    except UncertainResultError:
        logger.warning("[每日签到] 请求结果不确定，重新查询签到中心")
        try:
            refreshed = client.get_sign_state()
            confirmed = require_field(require_field(refreshed, "user", dict), "signed", bool)
        except RateLimitError:
            raise
        except ODDBAError as e:
            logger.error("[每日签到] 无法核验签到状态，跳过累签宝箱：{}", e)
            return {}, False, 1
        if confirmed:
            logger.success("[每日签到] 已通过当前状态确认今日已签到")
        else:
            logger.error("[每日签到] 尚未确认签到生效，本轮不再提交")
        return refreshed, False, int(not confirmed)
    except ODDBAError as e:
        logger.error("[每日签到] 签到失败：{}", e)
        return state, False, 1

    try:
        confirmed = require_field(data, "signed", bool)
    except ResponseError as e:
        confirmed = False
        logger.warning("[每日签到] 无法确认签到是否生效：{}", e)

    if not confirmed:
        logger.error("[每日签到] 服务端未确认签到生效，视为签到失败")
        return state, False, 1

    _show_rewards(data, "granted", "[每日签到]", "签到成功")
    return state, True, 0


def _confirm_claim(check: Callable[[], bool], label: str) -> bool:
    """写请求结果不确定时只查询核验，不在本轮再次提交。"""
    logger.warning("{} 请求结果不确定，重新查询领取状态", label)
    try:
        confirmed = check()
    except RateLimitError:
        raise
    except ODDBAError as e:
        logger.error("{} 无法核验领取状态：{}", label, e)
        return False
    if confirmed:
        logger.success("{} 已通过当前状态确认已领取", label)
    else:
        logger.error("{} 尚未确认领取生效，本轮不再提交", label)
    return confirmed


def _treasure_claimed(client: ODDBAClient, day: int) -> bool:
    for chest in require_field(client.get_sign_state(), "chests", list):
        if isinstance(chest, dict) and chest.get("day") == day:
            return require_field(chest, "claimed", bool)
    return False


def run_treasure(client: ODDBAClient, state: JsonObject, did_sign: bool) -> int:
    """执行累签宝箱领取，返回失败任务数量"""
    logger.info("[累签宝箱] 开始")
    try:
        chests = require_field(state, "chests", list)
    except ResponseError as e:
        logger.error("[累签宝箱] 无法读取宝箱列表：{}", e)
        return 1
    available: list[int] = []
    failures = 0

    for chest in chests:
        if not isinstance(chest, dict):
            failures += 1
            logger.warning("[累签宝箱] 累签宝箱条目不是对象，跳过：{}", chest)
            continue

        try:
            day = require_field(chest, "day", int)
            active = require_field(chest, "active", bool)
            claimed = require_field(chest, "claimed", bool)
            remain = require_field(chest, "remain", int)
        except ResponseError as e:
            failures += 1
            logger.warning("[累签宝箱] 累签宝箱条目结构异常，跳过：{}；错误：{}", chest, e)
            continue

        if not claimed and (active or (remain == 1 and did_sign)):
            available.append(day)

    if not available:
        if not failures:
            logger.info("[累签宝箱] 暂无可领取奖励")
        return failures

    for day in available:
        logger.info("[累签宝箱] 领取 {} 天宝箱", day)
        try:
            data = client.claim_treasure(day)
        except RateLimitError:
            raise
        except UncertainResultError:
            if not _confirm_claim(lambda: _treasure_claimed(client, day), f"[累签宝箱·{day} 天]"):
                failures += 1
            continue
        except ODDBAError as e:
            failures += 1
            logger.error("[累签宝箱] 领取 {} 天宝箱失败：{}", day, e)
            continue
        _show_rewards(data, "rewards", f"[累签宝箱·{day} 天]", "领取成功")

    return failures


def _daily_items(state: JsonObject) -> tuple[list[JsonObject], int]:
    """解析任务中心状态，返回有效每日任务条目与解析失败数量。"""
    sections = require_field(state, "sections", list)
    items: list[JsonObject] = []
    found_daily = False
    failures = 0

    for section in sections:
        if not isinstance(section, dict):
            failures += 1
            logger.warning("[每日任务] 任务分组不是对象，跳过：{}", section)
            continue
        try:
            key = require_field(section, "key", str)
        except ResponseError as e:
            failures += 1
            logger.warning("[每日任务] 无法识别任务分组，跳过：{}", e)
            continue
        if key != "daily":
            continue
        found_daily = True

        try:
            section_items = require_field(section, "items", list)
        except ResponseError as e:
            failures += 1
            logger.warning("[每日任务] 无法读取每日任务列表，跳过：{}", e)
            continue
        for item in section_items:
            if not isinstance(item, dict):
                failures += 1
                logger.warning("[每日任务] 每日任务条目不是对象，跳过：{}", item)
                continue

            try:
                require_field(item, "group", str)
                require_field(item, "id", str | int)
                require_field(item, "name", str)
                require_field(item, "status", str)
                require_field(item, "claimed", bool)
            except ResponseError as e:
                failures += 1
                logger.warning("[每日任务] 每日任务条目结构异常，跳过：{}；错误：{}", item, e)
                continue
            items.append(item)

    if not found_daily:
        raise ResponseError("任务中心缺少 daily 分组，不能确认每日任务状态")
    return items, failures


def _task_claimed(client: ODDBAClient, group: str, task_id: str | int) -> bool:
    items, _ = _daily_items(client.get_task_state())
    return any(
        item["group"] == group and item["id"] == task_id and item["claimed"] for item in items
    )


def run_task(client: ODDBAClient) -> int:
    """执行每日任务领取，返回失败任务数量"""
    logger.info("[每日任务] 开始")
    try:
        items, failures = _daily_items(client.get_task_state())
    except RateLimitError:
        raise
    except ODDBAError as e:
        logger.error("[每日任务] 获取任务中心状态失败，跳过每日任务奖励领取：{}", e)
        return 1

    claimed = 0

    for task in items:
        if task["status"] != "claimable" or task["claimed"]:
            continue

        group, task_id, name = task["group"], task["id"], task["name"]
        logger.info("[每日任务] 领取「{}」", name)
        try:
            data = client.claim_task(group, task_id)
        except RateLimitError:
            raise
        except UncertainResultError:
            if _confirm_claim(lambda: _task_claimed(client, group, task_id), f"[每日任务·{name}]"):
                claimed += 1
            else:
                failures += 1
            continue
        except ODDBAError as e:
            failures += 1
            logger.error("[每日任务] 领取「{}」失败：{}", name, e)
            continue

        claimed += 1
        _show_rewards(data, "rewards", f"[每日任务·{name}]", "领取成功")

    if not claimed and not failures:
        logger.info("[每日任务] 暂无可领取奖励")

    return failures
