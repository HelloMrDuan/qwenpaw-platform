# WeChat Customer Historical Gateway

状态：`RECOVERED_SOURCE_ONLY`。该目录保存微信客服（WeCom KF）Gateway 历史基线，尚未接入 Runtime。

## 来源与目录纠正

逻辑来源名称为 `channel-runtime-recovery-export/wecom-kf/`，ZIP 中实际路径为：

- `channel-runtime-recovery-export/wecom/wecom_kf_gateway_v345.py`；
- `channel-runtime-recovery-export/wecom/healthcheck_v345.sh`；
- `channel-runtime-recovery-export/docs/` 下的相关运行文档。

源码位于 `recovered/`，历史文档位于 `docs/`。没有修改 Gateway 逻辑。

## 原运行方式

- `healthcheck_v345.sh` 检查 `8798/healthz`；
- 无进程时后台执行 `python3 wecom_kf_gateway_v345.py`；
- Gateway 启动 HTTP Server、SQLite 和消息 polling。

本仓库不会执行该脚本。

## 依赖

- Python 3；
- `pycryptodome`；
- Pillow；
- SQLite、curl、nohup、pgrep；
- QwenPaw CLI 与 `sn_agent_runner.py`。

## 配置键

- `CORP_ID`、`APP_SECRET`、`TOKEN`；
- `AESKEY` / `AES_KEY`；
- `OPEN_KFID`；
- `QWENPAW_BIN`；
- DB、cursor、日志和生成目录路径。

真实 `.env` 没有迁移。

## 已知缺失

- `sn_agent_runner.py`；
- 源码实际引用的 `gateway-v32.db`；
- `sync_cursor_v345.json`；
- 历史 session/去重/图片状态；
- 脱敏 `.env.example`；
- 精确 Python dependency lock。

Schema 和兼容迁移逻辑内嵌在 Gateway 源码中；缺失的是历史数据和运行状态，不是 DDL 定义。

## 已排除

- `wecom/generated/` 历史探测图片；
- 数据库、WAL/SHM、cursor、日志和 secret。
