# CLAUDE.md

## 项目概述

Python 3.11+ 命令行脚本，用于自动完成 `sns.oddba.cn` 的每日签到、签到宝箱和每日任务奖励领取。

代码位于 `src/oddba_looter/`。无上传到 PyPI 的计划。

## 常用命令

```bash
uv sync
uv run oddba-looter
```

当前未配置测试、lint 或 CI。

## 开发约定

- 修改端点、请求参数、响应处理或选择器前，先阅读并同步更新 `docs/API-DOCS.md`。
- 不提交 `.env`、Cookie、日志或含账号信息的页面内容。
