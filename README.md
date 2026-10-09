# oddba-looter

逃离塔科夫中文社区 [sns.oddba.cn](https://sns.oddba.cn/) 的每日自动化脚本，按顺序执行以下操作：

1. 恢复缓存会话或登录
2. 每日签到
3. 领取累签宝箱
4. 领取每日任务奖励

不自动点赞、评论、发帖、打赏或发布签到心情；不处理成长任务；不补签。

> 免责声明：本项目仅供学习、研究与个人使用。因使用本项目造成的任何后果均由使用者自行承担。

## 环境要求

需要 Python 3.11+，推荐使用 [uv](https://docs.astral.sh/uv/) 管理 Python 和项目依赖。

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

## 配置

首次使用时复制 `.env.example` 为 `.env`，填入你的 oddba 用户名和密码：

```dotenv
ODDBA_USERNAME=你的用户名
ODDBA_PASSWORD='你的密码'
```

## 运行

使用 uv 运行：

```bash
uv run oddba-looter
```

返回值含义：`0` 一切正常，`1` 部分任务失败，`2` 限流中止或其它错误。

## 安全

请务必保管好以下文件和目录：

- `.env`：包含你的 oddba 账号密码
- `.cache/session.json`：网站认证 token 和账号摘要
- `logs/`：存放按月保存的日志

反馈问题时如果要分享日志，请脱敏后再分享。尤其是在开启了调试模式的情况下（`ODDBA_LOOTER_DEBUG=1`），日志中必定存在大量 Cookie 等敏感信息。

## 开发

使用 Ruff 检查代码并统一格式：

```bash
uv run ruff check . # 加 --fix 自动修复
uv run ruff format . # 加 --check 仅检查不修改文件
```

## Linux 定时运行

下面介绍如何让脚本在每天的 **00:30** 和 **12:30** 各运行一次。时间以服务器的本地时区为准，可先执行 `timedatectl` 检查服务器时区。

先手动运行一次虚拟环境中的 `oddba-looter`，确保脚本能够正常工作：

```bash
/home/yourname/oddba-looter/.venv/bin/oddba-looter
```

打开当前用户的 crontab：

```bash
crontab -e
```

添加一行：

```cron
30 0,12 * * * /home/yourname/oddba-looter/.venv/bin/oddba-looter > /dev/null 2>&1
```

保存后可使用以下命令确认任务已经写入：

```bash
crontab -l
```

请将示例路径替换为实际安装路径。上述配置会丢弃终端输出，常规日志仍保存在项目的 `logs/` 中。

如果后续更新了代码（如 `git pull`），请在项目目录再次执行 `uv sync`。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
