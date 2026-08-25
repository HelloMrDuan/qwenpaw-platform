# Channel Recovery Completeness Report

## 1. 审计目标

本报告用于判断 `channel-runtime-recovery-export.zip` 中的历史 Channel 资产是否完整到可以开始源码迁移。

本次只进行只读审计，不迁移代码、不执行恢复脚本、不连接 QwenPaw Runtime，也不读取或恢复真实 secret。

恢复包校验：

| 项目 | 结果 |
| --- | --- |
| 文件 | `channel-runtime-recovery-export.zip` |
| SHA-256 | `35fd917257b4bcb0862d7a76ef296985d265bc7a70f359601f2748e603aa8300` |
| ZIP 条目 | 3533 |
| 当前 Git 基线 | `8d84fb9cb31d2ea4a9321ee95aadf2300ee3f51a` |

## 2. 状态定义

| 状态 | 定义 |
| --- | --- |
| `READY_FOR_MIGRATION` | 核心源码、入口、可复现依赖元数据和脱敏配置模板均已找到；允许进入“只复制源码和文档”阶段 |
| `NEEDS_SOURCE` | 已有主体源码，但仍缺少被调用的自定义源码、依赖锁、安装元数据或配置模板 |
| `BLOCKED` | 核心实现或历史状态只存在于当前不可访问的外部系统，没有本地证据可继续恢复 |

本报告把“源码迁移完整性”和“历史运行状态恢复”分开。空库可由 schema 创建，不等于历史数据库、游标或会话已经恢复。

## 3. 扫描范围

已检查：

- `channel-runtime-recovery-export.zip` 的完整成员清单；
- `qwenpaw-platform-export.zip` 的完整成员清单；
- 当前仓库、Git 历史、`scripts/`、`digest/`、历史 `memory/` 记录；
- `D:\pyprograms`、Desktop、Downloads 和 Codex attachments 中的精确文件名候选；
- 恢复源码中的 import、入口、配置键、文件路径和 SQL DDL；
- 恢复报告与 ZIP 实际成员的一致性。

未检查：

- 云端 QwenPaw Runtime 文件系统；
- 原 NAS 挂载内容；
- 当前主机未暴露的 `/run`、`/workspace`、`/app`、`/root`、`/opt`；
- WSL 文件系统。

历史消息、Agent session JSONL、credentials 和数据库内容未读取。

## 4. 总体结论

| 组件 | 源码迁移状态 | 历史运行状态 | 主要缺口 |
| --- | --- | --- | --- |
| Hermes | `NEEDS_SOURCE` | `BLOCKED` | `sn_agent_runner.py`、`hermes.sh`、`pyproject.toml`、`uv.lock` |
| 微信客服（WeCom KF） | `NEEDS_SOURCE` | `BLOCKED` | Agent runner、数据库、游标、脱敏配置模板 |
| 企业微信（wecom-node） | `NEEDS_SOURCE` | `BLOCKED` | SDK 版本/依赖声明、组件 lock、Node 精确版本、Agent runner |
| Telegram Bridge | `NEEDS_SOURCE` | `BLOCKED` | Agent runner、Hermes wrapper、脱敏配置模板、历史 Python 环境锁 |
| WeChat MP Gateway | `NEEDS_SOURCE` | `BLOCKED` | 脱敏配置模板、启动制品、外部 QwenPaw 调用环境 |

当前没有组件满足严格的 `READY_FOR_MIGRATION` 门槛。主体源码已经找到，但在补齐或正式豁免缺口前，不建议开始源码目录迁移。

## 5. 跨组件关键缺口

### 5.1 `sn_agent_runner.py`

状态：`NEEDS_SOURCE`

检查结果：

- 恢复包成员：`NOT FOUND`；
- Workspace 导出包成员：`NOT FOUND`；
- 当前仓库和 `scripts/`：`NOT FOUND`；
- 当前机器高概率目录精确文件名搜索：`NOT FOUND`；
- 历史文档：多次引用，但只有文件名和运行路径，没有源码本体。

影响组件：

- Hermes `fast_route.py`；
- 企业微信 `wecom_bridge.mjs`；
- 微信客服 `wecom_kf_gateway_v345.py`；
- Telegram 的 Hermes/Agent 调用链。

该文件是多个 Channel 共用的 QwenPaw Agent 调用适配层。没有源码时，不能确认输入协议、超时、session 关联、输出格式和错误处理。

恢复来源建议：

1. 原 NAS 的 Hermes 目录；
2. 原 NAS 的 `wecom-kf` 目录；
3. 云端 workspace 的 custom files 或运行容器文件系统；
4. 旧容器镜像/卷、staging 快照或完整 Deployment Backup；
5. 历史部署主机上的同名文件。

禁止根据日志或 memory 记录重新编写该文件。

### 5.2 `hermes.sh`

状态：`NEEDS_SOURCE`

检查结果：

- 恢复包：`NOT FOUND`；
- Workspace 导出包：`NOT FOUND`；
- 当前仓库和机器精确搜索：`NOT FOUND`；
- `telegram_bridge.py`、`fast_route.py` 和 `wecom_bridge.mjs` 存在对它的历史引用。

Hermes 工程内存在正式 `hermes` Python CLI，但不能在不验证参数、环境和返回协议的情况下，把它直接视为历史 `hermes.sh` 的等价替代。

恢复来源建议：原 NAS Hermes 根目录、原安装器生成目录、旧服务工作目录或旧容器镜像。

## 6. Hermes

状态：`NEEDS_SOURCE`

### 6.1 已找到

| 资产 | 位置 | 结论 |
| --- | --- | --- |
| Hermes 工程 | `channel-runtime-recovery-export/hermes/hermes-agent-main/` | 主体源码存在 |
| 版本信息 | `hermes_cli/__init__.py` | 版本 `0.20.1`，发布日期 `2026.8.13` |
| CLI | `hermes-agent-main/hermes` | Python shebang，调用 `hermes_cli.main:main` |
| Gateway 入口 | `gateway/run.py` | 支持 `python -m gateway.run` |
| 服务命令 | `hermes_cli/main.py` | 支持 `hermes gateway` 及 start/stop/status/install |
| 容器入口 | Dockerfile、Compose、`docker/entrypoint-dispatch.sh` | 容器入口资料存在 |
| 辅助入口 | `fast_route.py`、`run_image_and_reply.sh` | 文件存在，但继续依赖缺失 runner |
| Python 版本 | `.python-version` | 3.11 |
| Node 版本 | `.nvmrc` | 26 |
| 配置示例 | `.env.example`、`cli-config.yaml.example` | 存在 |

### 6.2 Python 安装方式

恢复源码提供的安装/运行证据包括：

- README 使用 `uv pip install -e ".[all,dev]"`；
- Dockerfile 使用 `uv sync --frozen`；
- Dockerfile明确复制 `pyproject.toml` 与 `uv.lock`；
- CLI 可通过根 `hermes` 脚本或 Python module 运行；
- Dockerfile包含 Python、Node、ffmpeg、ripgrep、编译工具等系统依赖。

但是 ZIP 根目录实际没有：

- `pyproject.toml`；
- `uv.lock`；
- 根 `requirements.txt`；
- 可离线复现的安装器副本。

因此 README 和 Dockerfile描述了安装方式，但当前恢复包不能完成相同的 Python dependency resolve。

### 6.3 启动脚本与入口判断

| 候选 | 状态 | 说明 |
| --- | --- | --- |
| `hermes` | `FOUND` | 正式 CLI 入口 |
| `python -m gateway.run` | `FOUND` | Gateway Python 入口 |
| `hermes gateway start` | `FOUND` | 服务管理命令 |
| Docker entrypoint | `FOUND` | 容器入口完整 |
| `run_image_and_reply.sh` | `FOUND` | 只包装 `fast_route.py` |
| `hermes.sh` | `NOT FOUND` | 历史 Channel 调用的 wrapper 缺失 |
| `sn_agent_runner.py` | `NOT FOUND` | QwenPaw Agent 调用适配层缺失 |

### 6.4 缺失文件

- `sn_agent_runner.py`；
- `hermes.sh`；
- `pyproject.toml`；
- `uv.lock`；
- 与 0.20.1 源码对应的安装器/依赖快照。

### 6.5 恢复来源建议

1. 取得原 NAS `/run/.../nas/<volume>/hermes/` 的只读快照；
2. 从原 Hermes 0.20.1 发布源补齐依赖元数据，但必须先验证文件版本与恢复源码一致；
3. 从旧容器镜像提取 `/opt/hermes` 的 source manifest 和安装元数据；
4. 从旧虚拟环境导出 `pip freeze` 只作为校验，不用它替代缺失的项目 lock；
5. 从原安装目录恢复生成的 `hermes.sh` 和自定义 runner。

## 7. 微信客服（WeCom KF Gateway）

状态：`NEEDS_SOURCE`

历史运行状态：`BLOCKED`

### 7.1 已找到

| 资产 | 位置 | 结论 |
| --- | --- | --- |
| Gateway | `wecom/wecom_kf_gateway_v345.py` | 1144 行生产版本源码 |
| 健康检查 | `wecom/healthcheck_v345.sh` | `/healthz` 检查及无进程启动 |
| 历史端口 | 源码和脚本 | `8798` |
| 数据库初始化 | Gateway 内 `init_db()` | schema 与兼容 ALTER 逻辑内嵌 |
| 游标格式 | Gateway 内 `load_cursor()` / `save_cursor()` | JSON：`{"cursor": <string>}` |
| 运行文档 | `docs/wecom-*.md`、历史 memory | 部署和迁移记录存在 |

### 7.2 数据库文件核对

| 文件 | 结果 | 说明 |
| --- | --- | --- |
| `gateway-v345.db` | `NOT FOUND` | 恢复报告提到该名称，但源码没有引用它 |
| `gateway-v32.db` | `NOT FOUND` | V345 源码实际 `DB_PATH` 仍指向该名称 |
| `gateway-v32.db-wal` | `NOT FOUND` | 源码启用 WAL；历史运行时可能存在，但本地无文件证据 |
| `gateway-v32.db-shm` | `NOT FOUND` | 同上 |
| `schema.sql` | `NOT FOUND` | 不构成 schema 缺失，因为 DDL 内嵌于源码 |
| `migration.sql` | `NOT FOUND` | 迁移由 `PRAGMA table_info` + `ALTER TABLE` 内嵌实现 |

恢复报告与源码对数据库文件名存在冲突。迁移时必须以运行实例或数据库实际路径为准，不能把 `gateway-v345.db` 的文档名称当成已找到文件。

### 7.3 已确认数据库结构

`processed_messages`：

- `msgid TEXT PRIMARY KEY`；
- `external_userid TEXT`；
- `open_kfid TEXT`；
- `msgtype TEXT`；
- `content_hash TEXT`；
- `status TEXT NOT NULL DEFAULT 'completed'`；
- `created_at TEXT`；
- `updated_at TEXT`。

`conversation_messages`：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`；
- `external_userid TEXT NOT NULL`；
- `role TEXT NOT NULL`；
- `content TEXT NOT NULL`；
- `created_at TEXT NOT NULL`；
- 复合索引：`external_userid, created_at`。

`generated_images`：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`；
- `msgid TEXT NOT NULL`；
- `external_userid TEXT`；
- `open_kfid TEXT`；
- `prompt TEXT`；
- `image_path TEXT`；
- `upload_image_path TEXT`；
- `media_id TEXT`；
- `upload_status TEXT`；
- `send_status TEXT`；
- `created_at TEXT`；
- `msgid` 索引。

源码启用 `journal_mode=WAL` 和 `busy_timeout=5000`。

### 7.4 Cursor 与 session 存储

| 资产 | 结果 |
| --- | --- |
| `sync_cursor_v345.json` | `NOT FOUND`；历史 memory 只记录 NAS 路径和版本迁移 |
| Cursor schema | 已确认，仅保存 `cursor` 字符串 |
| Channel 对话历史 | 位于 SQLite `conversation_messages` 表；数据库缺失，因此历史内容不可恢复 |
| 消息去重状态 | 位于 `processed_messages` 表；数据库缺失 |
| 图片发送状态 | 位于 `generated_images` 表；数据库缺失 |
| QwenPaw session | Gateway schema没有独立 session 表；由外部 Agent runner/QwenPaw 负责，当前未恢复 |

### 7.5 启动依赖

- Python 3；
- `pycryptodome`：`Crypto.Cipher.AES`；
- Pillow：`PIL.Image`；
- SQLite Python 标准库；
- `curl`、`nohup`、`pgrep`；
- QwenPaw CLI/可执行入口；
- `sn_agent_runner.py`；
- 企业微信客服所需脱敏配置模板。

### 7.6 缺失文件

- `sn_agent_runner.py`；
- `gateway-v32.db` 及一致性备份所需的 WAL 状态；
- `sync_cursor_v345.json`；
- 微信客服 `.env.example`；
- 精确 Python dependency lock；
- 历史 QwenPaw session 映射说明。

`schema.sql` 和 `migration.sql` 虽未找到，但 schema/迁移逻辑已经内嵌，不列为必需源码缺口。

### 7.7 恢复来源建议

1. 原 NAS `/run/.../nas/<volume>/wecom-kf/`；
2. 原运行实例执行 SQLite 一致性 `.backup` 后导出的数据库；
3. 若直接复制 WAL 数据库，应在服务停止或受控 checkpoint 后同时核对 DB/WAL/SHM，不能只复制单个 DB 文件；
4. 原目录中的 `sync_cursor_v345.json`；
5. 云端 Secret 管理中恢复配置值，本仓库只保留 `.env.example`；
6. 原 QwenPaw workspace custom files 中恢复 `sn_agent_runner.py`。

## 8. 企业微信（wecom-node）

状态：`NEEDS_SOURCE`

### 8.1 当前文件

`hermes/wecom-node/` 实际只有：

- `wecom_bridge.mjs`；
- `bot.mjs`；
- `package.json`。

入口判断：

- `start_wecom_bridge.sh` 明确启动 `node wecom_bridge.mjs`；
- `wecom_bridge.mjs` 是历史主入口；
- `bot.mjs` 是另一 Bot 实现，不是恢复脚本选择的主入口。

### 8.2 Package 与 Node 完整性

| 检查项 | 结果 |
| --- | --- |
| `package.json` | `FOUND` |
| `package-lock.json`（wecom-node） | `NOT FOUND` |
| `npm-shrinkwrap.json` / pnpm/yarn lock | `NOT FOUND` |
| `dependencies` | 空；没有声明源码实际 import 的 SDK |
| `engines.node` | `NOT FOUND` |
| 历史恢复报告 | 记录 Node.js 18+ |
| 邻接 Hermes `.nvmrc` | Node 26；不能证明 wecom-node 历史运行时精确版本 |

Hermes 根目录的 `package-lock.json` 不包含 `@wecom/aibot-node-sdk`，也不属于外部 `hermes/wecom-node/` 组件，不能作为该 Bridge 的依赖锁。

### 8.3 SDK 与运行依赖

源码实际 import：

- `@wecom/aibot-node-sdk`；
- Node 内置 `fs`、`path`、`crypto`、`child_process`。

缺少：

- SDK 版本；
- SDK dependency declaration；
- wecom-node lockfile；
- 组件自己的 Node 版本锁；
- `sn_agent_runner.py`；
- `hermes.sh`/Hermes 历史调用 wrapper；
- 企业微信 `.env.example`。

识别出的配置键包括 `WECOM_BOT_ID`、`WECOM_BOT_SECRET`、`HERMES_HOME` 及 SenseNova 相关键。只记录键名，不恢复值。

### 8.4 恢复来源建议

1. 原 NAS `/run/.../nas/<volume>/hermes/wecom-node/`；
2. 原 `node_modules/@wecom/aibot-node-sdk/package.json`，仅用于确认精确 SDK 版本；
3. 原 npm cache、lockfile 或部署日志；
4. 原服务环境的 `node --version` 与 `npm --version` 记录；
5. 原 Secret 管理恢复配置值，Git 只保存 `.env.example`；
6. 不安装“最新 SDK”来代替缺失版本锁。

## 9. Telegram Bridge

状态：`NEEDS_SOURCE`

### 9.1 主程序与启动方式

| 资产 | 结果 |
| --- | --- |
| `telegram_bridge_main.py` | `FOUND`；恢复报告和启动脚本选择的主程序 |
| `telegram_bridge.py` | `FOUND`；另一历史实现，包含 Unix `fcntl` 文件锁 |
| `start_bridge.sh` | `FOUND` |
| 启动方式 | `bash start_bridge.sh`，内部执行 `python3 telegram_bridge_main.py` |
| PID/日志 | 由启动脚本生成；属于运行状态，不迁移 |

主程序使用 `urllib` 直接调用 Telegram HTTP API，并通过 subprocess 调用 `run_image_and_reply.sh`。

### 9.2 `python-telegram-bot` 核对

恢复报告声称历史环境使用 `python-telegram-bot 22.8`，但静态源码和依赖文件的结果是：

- 两个 Telegram Bridge 均没有 `import telegram`；
- 没有 `telegram.ext` 使用；
- 当前实现通过 Python 标准库 `urllib` 调用 Bot API；
- 恢复包没有为该 Bridge 提供 requirements/lock；
- 恢复包其他 manifest 中也没有找到 `python-telegram-bot` 引用。

结论：`python-telegram-bot 22.8` 只有恢复报告证据，不能确认是当前 `telegram_bridge_main.py` 的执行依赖。迁移时不得仅依据报告新增该库。

若要求复刻历史 Python 环境，应从原 venv 的 package metadata 或 `pip freeze` 确认它是否只是历史安装项、旧实现依赖或其他组件依赖。

### 9.3 配置模板

识别出的配置键：

- 主入口：`TELEGRAM_BOT_TOKEN`、`HERMES_HOME`；
- 备用实现：额外使用 `TELEGRAM_ALLOWED_USERS`；
- offset、state、lock、日志路径。

实际 `.env` 已排除，恢复包没有 Telegram `.env.example`。

### 9.4 缺失文件

- `sn_agent_runner.py`；
- `hermes.sh`；
- Telegram `.env.example`；
- 历史 Python dependency lock/venv metadata；
- 与历史 Bot token 配套的 Secret 管理记录（只应恢复到 Secret 系统）。

`run_image_and_reply.sh` 和 `fast_route.py` 已找到，但其下游仍引用缺失的 runner，因此调用链没有闭合。

### 9.5 恢复来源建议

1. 原 NAS Hermes 根目录；
2. 原 Telegram Bridge venv/package metadata；
3. 云端 custom files、容器镜像或 staging 快照；
4. 原 Secret 管理中的 token/allow list；
5. 不根据恢复报告直接引入 `python-telegram-bot`。

## 10. WeChat MP Gateway

状态：`NEEDS_SOURCE`

该组件不在本轮重点清单中，但恢复包包含两个版本，因此一并核对：

| 检查项 | 结果 |
| --- | --- |
| `wechat_mp_gateway.py` | `FOUND`，历史端口 8799 |
| `wechat_mp_gateway_v2.py` | `FOUND`，候选端口 8800 |
| Python 第三方依赖 | 未发现；以标准库为主 |
| 启动脚本 | `NOT FOUND`；恢复报告只记录直接 `python3` 启动 |
| `mp-secret.env` | `NOT FOUND`，按敏感信息规则排除 |
| QwenPaw CLI/API | 外部依赖，当前不在恢复包内 |

缺失文件：脱敏配置模板、历史启动/守护脚本、外部 QwenPaw 调用环境说明。

恢复来源建议：原 WeChat MP 工作目录、云端 Secret 管理、旧服务定义和运行容器。

## 11. 缺失文件总表

| 缺失资产 | 影响组件 | 优先级 | 当前状态 |
| --- | --- | --- | --- |
| `sn_agent_runner.py` | Hermes、WeCom KF、wecom-node、Telegram | P0 | `NEEDS_SOURCE` |
| `hermes.sh` | Hermes、wecom-node、Telegram 备用链路 | P0 | `NEEDS_SOURCE` |
| Hermes `pyproject.toml` | Hermes | P0 | `NEEDS_SOURCE` |
| Hermes `uv.lock` | Hermes | P0 | `NEEDS_SOURCE` |
| wecom-node lockfile | 企业微信 | P0 | `NEEDS_SOURCE` |
| `@wecom/aibot-node-sdk` 精确版本 | 企业微信 | P0 | `NEEDS_SOURCE` |
| `gateway-v32.db` 一致性备份 | 微信客服历史状态 | P0 | `BLOCKED` |
| `sync_cursor_v345.json` | 微信客服历史状态 | P0 | `BLOCKED` |
| 各组件 `.env.example` | WeCom KF、wecom-node、Telegram、WeChat MP | P1 | `NEEDS_SOURCE` |
| 历史 Python/Node 环境锁 | 多组件 | P1 | `NEEDS_SOURCE` |
| WeChat MP 服务脚本 | WeChat MP | P1 | `NEEDS_SOURCE` |

## 12. 恢复优先顺序

1. 获取原 NAS Hermes 与 `wecom-kf` 目录的只读快照；
2. 优先恢复 `sn_agent_runner.py` 和 `hermes.sh`，闭合跨 Channel 调用链；
3. 补齐 Hermes 0.20.1 对应的 `pyproject.toml`、`uv.lock`；
4. 确认企业微信 SDK 版本、Node 版本和 lockfile；
5. 对微信客服数据库执行一致性导出，并同时恢复 cursor；
6. 从 Secret 管理恢复配置值，在仓库中仅生成脱敏模板；
7. 重新运行完整性审计；
8. 只有组件状态变为 `READY_FOR_MIGRATION` 后，才进入源码基线迁移。

## 13. Git 与安全约束

后续恢复时不得提交：

- 原始 `.env`；
- bot token、secret、API key；
- SQLite 数据库、WAL/SHM；
- cursor、session、聊天记录；
- PID、日志和生成文件；
- 原 NAS 的目录标识或挂载凭据。

恢复 ZIP 继续作为本地审计输入，不加入 Git。任何新增恢复文件应先做 SHA-256 清单、敏感信息检查和来源记录，再决定是否进入源码迁移提交。
