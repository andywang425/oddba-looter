from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
LOG_DIR = PROJECT_ROOT / "logs"
SESSION_FILE = PROJECT_ROOT / ".cache" / "session.json"

BASE_URL = "https://sns.oddba.cn"
COOKIE_DOMAIN = "sns.oddba.cn"
TOKEN_COOKIE = "lightsns_token"
HOME_PAGE = f"{BASE_URL}/"
SIGN_PAGE = f"{BASE_URL}/sign"
TASK_PAGE = f"{BASE_URL}/task-center"
LOGIN_ACTION = "/api/user/login"
HEADER_ACTION = "/api/pc/header/index"
SIGN_INIT = "/module/pc/page/jinsom-pc-page-default-sign/init"
SIGN_ACTION = "/api/user/checkin"
SIGN_TREASURE_ACTION = "/api/user/checkin-treasure"
TASK_INIT = "/api/task-center/init"
TASK_ACTION = "/api/task-center/claim"

IMPERSONATE = "chrome"
REQUEST_TIMEOUT = 30
RETRIES = 2
RETRY_DELAY = 1


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    username: str = field(repr=False)
    password: str = field(repr=False)
    debug: bool = False

    @property
    def account_hash(self) -> str:
        return hashlib.sha256(f"{BASE_URL}\0{self.username}".encode("utf-8")).hexdigest()


def load_settings() -> Settings:
    if not ENV_FILE.is_file():
        raise ConfigError("项目根目录缺少 .env 文件")

    try:
        values = dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False)
    except (OSError, UnicodeError):
        raise ConfigError("无法读取项目根目录的 .env，请检查文件编码和访问权限")

    # 键存在但没写 `=` 时 python-dotenv 会给出 None，统一归一化为空串
    def value_of(key: str) -> str:
        return values.get(key) or ""

    username = value_of("ODDBA_USERNAME").strip()
    password = value_of("ODDBA_PASSWORD")
    if not username or not password:
        raise ConfigError("请在项目根目录 .env 中配置 ODDBA_USERNAME 和 ODDBA_PASSWORD")

    debug_value = value_of("ODDBA_LOOTER_DEBUG").strip()
    if debug_value not in {"", "0", "1"}:
        raise ConfigError("ODDBA_LOOTER_DEBUG 需为 1、0 或留空")

    return Settings(username, password, debug_value == "1")
