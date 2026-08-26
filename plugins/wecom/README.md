# WeCom Historical Bridge

> 状态：`LEGACY / FALLBACK / REFERENCE ONLY`。QwenPaw v2.1.0 已提供生产默认的内置企业微信 Channel；禁止继续将历史 Bridge 开发为生产 `BaseChannel` 或自定义 Channel 注册入口。

该目录只保存历史企业微信 Bridge 源码和恢复证据，不替代内置企业微信 Channel，也不作为生产部署候选。

## 来源与目录纠正

逻辑来源名称为 `channel-runtime-recovery-export/wecom-node/`，ZIP 中的实际路径为：

- `channel-runtime-recovery-export/hermes/wecom-node/`；
- `channel-runtime-recovery-export/telegram/start_wecom_bridge.sh`。

迁移后：

- `recovered/wecom-node/wecom_bridge.mjs`：历史主入口；
- `recovered/wecom-node/bot.mjs`：另一 Bot 实现；
- `recovered/wecom-node/package.json`：原始 package 描述；
- `recovered/start_wecom_bridge.sh`：原后台启动脚本。

来源文件没有修改业务逻辑。

## 原运行方式

```text
bash start_wecom_bridge.sh
```

脚本内部执行 `node wecom_bridge.mjs`。PID 和日志属于运行状态，没有迁移。

## 依赖

- Node.js；历史恢复报告记录 18+，相邻 Hermes 工程使用 26，但组件未锁定精确版本；
- `@wecom/aibot-node-sdk`；
- Node 内置 `fs`、`path`、`crypto`、`child_process`；
- Hermes/Agent runner。

## 配置键

- `WECOM_BOT_ID`；
- `WECOM_BOT_SECRET`；
- `HERMES_HOME`；
- SenseNova 相关 API/模型键。

真实 `.env` 没有迁移。

## 已知缺失

- wecom-node 的 `package-lock.json` 或其他 lockfile；
- `package.json` 中的 SDK dependency declaration；
- `@wecom/aibot-node-sdk` 精确版本；
- 组件级 Node 版本锁；
- `sn_agent_runner.py` 和历史 Hermes wrapper；
- 脱敏 `.env.example`。

在补齐依赖版本前，不得执行 `npm install` 选择最新版 SDK。
