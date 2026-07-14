# oddba-looter

逃离塔科夫中文社区 [sns.oddba.cn](https://sns.oddba.cn/) 的每日自动化脚本，按顺序执行以下操作：

1. 每日签到
2. 领取签到宝箱奖励
3. 领取每日任务奖励

> 免责声明：本项目仅供学习、研究与个人使用。因使用本项目造成的任何后果均由使用者自行承担。

## 环境要求

推荐使用 [uv](https://docs.astral.sh/uv/) 管理 Python 和项目依赖

## 安装

克隆仓库并切换到项目目录：

```bash
git clone https://github.com/andywang425/oddba-looter
cd oddba-looter
```

使用 uv 创建虚拟环境并安装依赖：

```bash
uv sync
```

## 获取登录 Cookie

请先在浏览器中登录 [ODDBA 社区](https://sns.oddba.cn/)，然后按照以下步骤获取 Cookie：

1. 按 `F12` 打开浏览器开发者工具。
2. 以 Chrome 浏览器为例：点击 **Application（应用）**，找到 **Storage（存储）** → **Cookie** → `https://sns.oddba.cn`。
3. 在 Cookie 列表中找到名称以 `wordpress_logged_in_` 开头的项目。
4. 将 Cookie 的名称和值以 `名称=值` 的格式拼接，形如：`wordpress_logged_in_xxx=yyy`，配置时会用到。

Cookie 等同于登录凭证，请不要将其分享给任何人。若退出登录、修改密码或登录过期，需要重新获取 Cookie。

## 配置

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，将上一步获取的完整 Cookie 填入 `ODDBA_COOKIE`：

```dotenv
ODDBA_COOKIE=wordpress_logged_in_xxx=yyy
```

通常只需要一个 `wordpress_logged_in_xxx` Cookie。需要填写多个 Cookie 时，使用英文分号 `;` 分隔：

```dotenv
ODDBA_COOKIE=cookie_a=value_a; cookie_b=value_b
```

## 运行

使用 uv 运行：

```bash
uv run oddba-looter
```

日志文件位于 `logs/` 目录，按月切分。

## Linux 定时运行

下面介绍如何让脚本在每天的 **00:30** 和 **12:30** 各运行一次。时间以服务器的本地时区为准，可先执行 `timedatectl` 检查服务器时区。

先进入项目目录（如 `/home/yourname/oddba-looter`），手动运行一次虚拟环境中的 `oddba-looter`，确保能够正常工作：

```bash
cd /home/yourname/oddba-looter
./.venv/bin/oddba-looter
```

打开当前用户的 crontab：

```bash
crontab -e
```

添加一行：

```cron
30 0,12 * * * cd /home/yourname/oddba-looter && ./.venv/bin/oddba-looter > /dev/null 2>&1
```

保存后可使用以下命令确认任务已经写入：

```bash
crontab -l
```

如果后续更新了代码（如 `git pull`），请再执行一次 `uv sync`。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
