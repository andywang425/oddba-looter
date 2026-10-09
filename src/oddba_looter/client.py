from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, TypeVar

from curl_cffi import CurlHttpVersion, requests
from curl_cffi.requests.exceptions import RequestException
from loguru import logger

from .config import (
    BASE_URL,
    COOKIE_DOMAIN,
    HEADER_ACTION,
    HOME_PAGE,
    IMPERSONATE,
    LOGIN_ACTION,
    REQUEST_TIMEOUT,
    RETRIES,
    RETRY_DELAY,
    SESSION_FILE,
    SIGN_ACTION,
    SIGN_INIT,
    SIGN_PAGE,
    SIGN_TREASURE_ACTION,
    TASK_ACTION,
    TASK_INIT,
    TASK_PAGE,
    TOKEN_COOKIE,
    Settings,
)

JsonObject = dict[str, Any]
T = TypeVar("T")


class ODDBAError(Exception):
    """脚本执行异常基类"""


class NetworkError(ODDBAError):
    """网络错误"""


class HTTPError(NetworkError):
    """HTTP 状态码错误"""


class RateLimitError(HTTPError):
    """站点限流，必须停止本轮所有请求"""


class UncertainResultError(NetworkError):
    """写请求可能已生效，不能直接重发"""


class ResponseError(ODDBAError):
    """响应结构错误"""


class AuthenticationError(ODDBAError):
    """身份认证错误"""


class BusinessError(ODDBAError):
    """业务错误"""


def require_field(data: JsonObject, key: str, expected: type[T]) -> T:
    value = data.get(key)
    if not isinstance(value, expected):
        raise ResponseError(f"响应字段 {key} 缺失或类型异常")
    return value


def require_success(result: JsonObject, operation: str) -> None:
    if result["code"] != 1:
        message = result["msg"] or "服务端未提供原因"
        raise BusinessError(f"{operation}失败（code={result['code']}）：{message}")


def response_data(result: JsonObject, operation: str) -> JsonObject:
    require_success(result, operation)
    return require_field(result, "data", dict)


class ODDBAClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._reauthenticated = False
        self._rate_limited = False
        self.session = requests.Session(
            impersonate=IMPERSONATE,
            http_version=CurlHttpVersion.V2TLS,
            timeout=REQUEST_TIMEOUT,
            retry=0,
            allow_redirects=False,
            raise_for_status=False,
            debug=settings.debug,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": BASE_URL,
            },
        )

    def __enter__(self) -> ODDBAClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.session.close()

    def _post(
        self,
        path: str,
        *,
        referer: str,
        data: dict[str, str | int] | None = None,
    ) -> JsonObject:
        if self._rate_limited:
            raise RateLimitError("站点已限流，本轮不再发送请求")
        read_only = path in {HEADER_ACTION, SIGN_INIT, TASK_INIT}
        retries = RETRIES if read_only else 0
        for attempt in range(retries + 1):
            started = time.monotonic()
            try:
                response = self.session.post(
                    BASE_URL + path, data=data, headers={"Referer": referer}
                )
            except RequestException as e:
                logger.debug("[HTTP] POST {} 网络异常类型={}", path, e)
                if attempt < retries:
                    logger.warning("请求遇到网络异常，准备重试 {}/{}", attempt + 1, RETRIES)
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                if not read_only:
                    raise UncertainResultError(f"请求结果不确定，未自动重发：{path}") from e
                raise NetworkError(f"网络请求失败：{path}")

            logger.debug(
                "[HTTP] POST {} 状态={} 协议={} 耗时={:.3f}s 响应体：{}",
                path,
                response.status_code,
                response.http_version,
                time.monotonic() - started,
                response.text,
            )

            if not 200 <= response.status_code < 300:
                if response.status_code == 429:
                    self._rate_limited = True
                    raise RateLimitError("站点返回 HTTP 429，已停止本轮请求，请稍后再运行")
                retryable = response.status_code == 408 or response.status_code >= 500
                if retryable and attempt < retries:
                    logger.warning(
                        "返回 HTTP {}，准备重试 {}/{}",
                        response.status_code,
                        attempt + 1,
                        RETRIES,
                    )
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                if retryable and not read_only:
                    raise UncertainResultError(
                        f"HTTP {response.status_code}，请求结果不确定：{path}"
                    )
                raise HTTPError(f"HTTP {response.status_code}：{path}")

            try:
                result = response.json()
            except ValueError:
                raise ResponseError(f"接口未返回有效 JSON：{path}")

            if not isinstance(result, dict):
                raise ResponseError(f"接口 JSON 信封不是对象：{path}")

            require_field(result, "code", int)
            require_field(result, "msg", str | None)
            return result

    def _request(
        self,
        path: str,
        *,
        referer: str,
        data: dict[str, str | int] | None = None,
    ) -> JsonObject:
        result = self._post(path, referer=referer, data=data)
        if result["code"] == 401:
            if self._reauthenticated:
                raise AuthenticationError("会话再次失效，本次不再自动登录，请在浏览器检查账号状态")
            self._reauthenticated = True
            logger.warning("会话已过期，重新认证一次后重发被拒绝的请求")
            self._login()
            result = self._post(path, referer=referer, data=data)
            if result["code"] == 401:
                raise AuthenticationError("重新认证后请求仍被拒绝，已停止")
        return result

    def _install_token(self, token: str) -> None:
        self.session.cookies.delete(TOKEN_COOKIE)
        self.session.cookies.set(TOKEN_COOKIE, token, domain=COOKIE_DOMAIN, path="/", secure=True)

    def _load_cached_token(self) -> str | None:
        try:
            cache = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, UnicodeError):
            logger.warning("会话缓存无法读取或已损坏，将重新登录")
            return None
        if not isinstance(cache, dict):
            logger.warning("会话缓存格式异常，将重新登录")
            return None
        if cache.get("account_hash") != self.settings.account_hash:
            logger.info("会话缓存与当前账号不匹配，不复用旧会话")
            return None
        return cache.get("token")

    def _save_token(self, token: str) -> None:
        temporary: Path | None = None
        try:
            SESSION_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=SESSION_FILE.parent,
                prefix=".session-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump({"account_hash": self.settings.account_hash, "token": token}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, SESSION_FILE)
            temporary = None
        except OSError:
            logger.warning("无法保存会话缓存，本次会话仍可使用；请检查 .cache 目录权限")
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.warning("未能清理会话临时文件，请妥善保护 .cache 目录")

    def _is_logged_in(self) -> bool:
        result = self._post(HEADER_ACTION, referer=HOME_PAGE)
        if result["code"] == 401:
            return False
        return require_field(response_data(result, "验证登录状态"), "is_login", bool)

    def authenticate(self) -> None:
        token = self._load_cached_token()
        if token:
            self._install_token(token)
            if self._is_logged_in():
                logger.success("已恢复并验证缓存会话")
                return
            logger.info("缓存会话已失效，将重新登录")
        self._login()

    def _login(self) -> None:
        self.session.cookies.delete(TOKEN_COOKIE)
        logger.info("正在登录")
        result = self._post(
            LOGIN_ACTION,
            referer=HOME_PAGE,
            data={
                "account": self.settings.username,
                "password": self.settings.password,
                "captcha_token": "",
            },
        )
        if result["code"] != 1:
            raise AuthenticationError(
                "登录失败，请检查账号密码或在浏览器中处理验证码；本次不再尝试密码"
            )
        token = require_field(response_data(result, "登录"), "token", str)
        self._install_token(token)
        if not self._is_logged_in():
            raise AuthenticationError("登录后仍未确认有效会话，已停止")
        self._save_token(token)
        logger.success("登录成功，已验证会话")

    def get_sign_state(self) -> JsonObject:
        return response_data(self._request(SIGN_INIT, referer=SIGN_PAGE), "初始化签到中心")

    def do_sign(self) -> JsonObject:
        return response_data(
            self._request(SIGN_ACTION, referer=SIGN_PAGE, data={"mark": "", "captcha_token": ""}),
            "每日签到",
        )

    def claim_treasure(self, day: int) -> JsonObject:
        return response_data(
            self._request(SIGN_TREASURE_ACTION, referer=SIGN_PAGE, data={"day": day}),
            "领取累签宝箱",
        )

    def get_task_state(self) -> JsonObject:
        return response_data(self._request(TASK_INIT, referer=TASK_PAGE), "初始化任务中心")

    def claim_task(self, group: str, task_id: str | int) -> JsonObject:
        return response_data(
            self._request(
                TASK_ACTION, referer=TASK_PAGE, data={"group": group, "task_id": task_id}
            ),
            "领取每日任务奖励",
        )
