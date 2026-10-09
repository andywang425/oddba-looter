# AGENTS.md

## 项目概述

Python 3.11+ 命令行脚本，用于自动完成 `sns.oddba.cn` 的每日签到、累签宝箱和每日任务奖励领取。

代码位于 `src/oddba_looter/`。无上传到 PyPI 的计划。

## 常用命令

```bash
uv sync
uv run oddba-looter
uv run ruff check .
uv run ruff format .
```

当前未配置测试或 CI。Lint 和格式化使用 Ruff。

## 开发约定

- 修改端点、请求参数或响应处理前，先阅读并同步更新 `docs/API-DOCS.md`。

## 安全约定

- 敏感信息：`.env`、Cookie、日志、请求 id、订单 id、账号信息，以及任何可通过其关联到具体账号的信息均被视为敏感信息。
- 不提交敏感信息。如果需要作为示例存在，要做脱敏。
- 金币和道具卡是账号的重要资产。如果你想做某个需要消耗金币或道具卡的操作，需要先征得用户同意后再继续。
- 向站点发送请求时需控制请求频率，否则可能导致 ip 被暂时封禁。
