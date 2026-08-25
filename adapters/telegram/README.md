# Telegram Historical Adapter Source

状态：`RECOVERED_SOURCE_ONLY`。该目录保存历史 Telegram Bridge，尚未实现 Extension Contract 包装，也未接入 Runtime。

## 来源与目录纠正

逻辑来源描述为 `channel-runtime-recovery-export/hermes/telegram_bridge*`，ZIP 中实际路径为：

- `channel-runtime-recovery-export/telegram/telegram_bridge.py`；
- `channel-runtime-recovery-export/telegram/telegram_bridge_main.py`；
- `channel-runtime-recovery-export/telegram/start_bridge.sh`。

来源文件原样放入 `recovered/`。`telegram_bridge.pid` 没有迁移。

## 原运行方式

```text
bash start_bridge.sh
```

启动脚本执行 `python3 telegram_bridge_main.py`，并管理日志与 PID。

## 依赖

- Python 标准库 `urllib`、JSON、subprocess、pathlib、time；
- `telegram_bridge.py` 额外使用 Unix `fcntl`；
- `HERMES_HOME`、`run_image_and_reply.sh` 和下游 Agent runner；
- Telegram Bot HTTP API。

恢复报告提到 `python-telegram-bot 22.8`，但两个恢复源码都没有 import 该库，当前实现直接使用 `urllib`。不得仅依据历史报告新增该依赖。

## 配置键与缺失项

配置键：

- `TELEGRAM_BOT_TOKEN`；
- `TELEGRAM_ALLOWED_USERS`（备用实现）；
- `HERMES_HOME`；
- state、offset、lock 和日志路径。

缺失：

- `sn_agent_runner.py`；
- 历史 `hermes.sh`；
- Telegram `.env.example`；
- 历史 Python environment lock。

真实 token、PID、日志和 offset 状态没有迁移。
