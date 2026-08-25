# Channel Recovery Migration Plan

## 1. 目标与边界

本计划用于把 `channel-runtime-recovery-export.zip` 中已经存在的 Channel/Gateway 实现迁移到 QwenPaw Extension Architecture。

本阶段只做审计和迁移规划。后续第一阶段只允许复制源码、已有配置模板和文档，不执行以下操作：

- 不修改恢复源码的业务逻辑；
- 不重写 Channel、Gateway 或 Bridge；
- 不接入 QwenPaw Runtime；
- 不修改 Agent 或 PDF Editor；
- 不启动进程、不连接 Telegram/企业微信/微信服务器；
- 不迁移 token、secret、数据库、日志、PID 或用户数据。

恢复包校验信息：

| 项目 | 值 |
| --- | --- |
| 文件 | `channel-runtime-recovery-export.zip` |
| SHA-256 | `35fd917257b4bcb0862d7a76ef296985d265bc7a70f359601f2748e603aa8300` |
| ZIP 根目录 | `channel-runtime-recovery-export/` |
| 条目数量 | 3533 |
| 审计方式 | 只读成员清单与源码静态分析；未执行任何恢复脚本 |

## 2. 总体判断

恢复包确认包含以下历史实现：

| 组件 | 实现状态 | 配置状态 | 运行制品状态 | 指定迁移根目录 |
| --- | --- | --- | --- | --- |
| Hermes | 完整工程源码及本地辅助脚本 | 有 `.env.example`、CLI 配置示例和 Docker 配置 | 部分外部 runner 缺失 | `plugins/hermes` |
| 企业微信 Bridge | `wecom_bridge.mjs`、`bot.mjs` 及启动脚本 | 实际 `.env` 已排除；无独立示例模板 | 日志/PID 不迁移，外部 runner 缺失 | `plugins/wecom` |
| 微信客服 Gateway | `wecom_kf_gateway_v345.py` 及健康检查脚本 | 实际 `.env` 已排除；无示例模板 | 数据库、游标和日志未包含 | `plugins/wechat-customer` |
| WeChat MP Gateway | 两版 Python Gateway | `mp-secret.env` 已排除；无示例模板 | 无启动脚本和运行状态 | `plugins/wechat-mp`（补充建议目录） |
| Telegram Bridge | 两个 Python Bridge 版本及启动脚本 | 实际 `.env` 已排除；无示例模板 | PID 文件存在但禁止迁移，外部 runner 缺失 | `adapters/telegram` |

用户给定的 Hermes、企业微信、微信客服和 Telegram 映射保持不变。恢复包还包含独立的 WeChat MP Gateway；为避免与“微信客服”混淆，本计划将其单列到 `plugins/wechat-mp`。该补充目录只作为迁移目标，不代表已经接入 Runtime。

恢复包还包含：

- `configs/wecom-public-agent.json`；
- `configs/wecom-public-skill.json`。

两者属于完整 Workspace/Agent 配置参考，不是单一插件的脱敏配置模板。第一阶段不复制、不合并到现有 `configs/`，只在迁移 README 中记录其来源；这样可以避免意外修改 Agent 或把 Runtime 配置当成 Extension 配置。

## 3. 第一阶段目录策略

第一阶段在目标根目录下使用 `recovered/` 保存原始布局，避免为了符合新接口而修改 import、相对路径或启动脚本：

```text
plugins/
├── hermes/
│   ├── recovered/
│   │   ├── hermes-agent-main/
│   │   ├── fast_route.py
│   │   └── run_image_and_reply.sh
│   └── README.md
├── wecom/
│   ├── recovered/
│   │   ├── start_wecom_bridge.sh
│   │   └── wecom-node/
│   └── README.md
├── wechat-customer/
│   ├── recovered/
│   │   ├── wecom_kf_gateway_v345.py
│   │   └── healthcheck_v345.sh
│   └── README.md
└── wechat-mp/
    ├── recovered/
    │   ├── wechat_mp_gateway.py
    │   └── wechat_mp_gateway_v2.py
    └── README.md

adapters/
└── telegram/
    ├── recovered/
    │   ├── telegram_bridge.py
    │   ├── telegram_bridge_main.py
    │   └── start_bridge.sh
    └── README.md
```

`recovered/` 表示来源代码的只读基线。未来 Extension Contract 包装层应放在目标根目录的独立文件中，不得直接修改 `recovered/` 基线。

## 4. Hermes

### 4.1 当前源码位置

| 恢复包位置 | 类型 | 说明 |
| --- | --- | --- |
| `channel-runtime-recovery-export/hermes/hermes-agent-main/` | 完整多语言工程 | 包含 Agent、Gateway、CLI、Desktop、Web、Docker、Nix 和测试等目录 |
| `channel-runtime-recovery-export/hermes/fast_route.py` | Python 辅助入口 | 历史快速路由脚本 |
| `channel-runtime-recovery-export/hermes/run_image_and_reply.sh` | Shell 包装脚本 | 调用外部 Python runner |
| `channel-runtime-recovery-export/hermes/hermes-agent-main/README*.md` | 文档 | 上游安装与运行说明 |

### 4.2 原运行方式

恢复工程文档给出的主要运行入口包括：

- `hermes`：CLI 入口；
- `hermes gateway`：消息 Gateway；
- `hermes gateway setup` / `hermes gateway start`：Gateway 配置与启动；
- Docker Compose、Dockerfile 和 Nix 配置；
- `fast_route.py`、`run_image_and_reply.sh`：历史环境中的辅助调用链。

第一阶段不选择或启动任何入口，只保留来源文件。

### 4.3 依赖

| 依赖 | 审计结果 |
| --- | --- |
| Python | `.python-version` 指定 3.11 |
| Node.js | `.nvmrc` 指定 26 |
| 系统工具 | README 提到 `uv`、Git Bash/shell、`ripgrep`、`ffmpeg` 等 |
| Web/Desktop | 根 `package.json`、workspace package 和 `package-lock.json` 存在 |
| 容器 | Dockerfile、Linux/Windows Compose、Nix 配置存在 |
| Python 安装元数据 | README 使用 `uv pip install -e ".[all,dev]"`，但恢复包根目录未找到 `pyproject.toml`、根 `requirements.txt` 或 `uv.lock`；属于恢复缺口 |
| 外部运行文件 | `hermes.sh`、`sn_agent_runner.py` 在源码中被引用，但恢复包未包含 |

### 4.4 配置模板

已找到：

- `hermes-agent-main/.env.example`；
- `hermes-agent-main/cli-config.yaml.example`；
- `hermes-agent-main/docker-compose.yml`；
- `hermes-agent-main/docker-compose.windows.yml`。

真实 `.env` 和密钥不在恢复包内。第一阶段只复制已有示例文件，不补填任何值。

### 4.5 迁移目标

| 来源 | 目标 |
| --- | --- |
| `hermes/hermes-agent-main/` | `plugins/hermes/recovered/hermes-agent-main/` |
| `hermes/fast_route.py` | `plugins/hermes/recovered/fast_route.py` |
| `hermes/run_image_and_reply.sh` | `plugins/hermes/recovered/run_image_and_reply.sh` |
| Hermes 审计说明 | `plugins/hermes/README.md` |

## 5. 企业微信 Bridge

### 5.1 当前源码位置

| 恢复包位置 | 类型 | 说明 |
| --- | --- | --- |
| `channel-runtime-recovery-export/hermes/wecom-node/wecom_bridge.mjs` | Node.js Bridge | 企业微信消息到 Hermes/Agent runner 的主 Bridge |
| `channel-runtime-recovery-export/hermes/wecom-node/bot.mjs` | Node.js Bot | 企业微信 Bot 实现 |
| `channel-runtime-recovery-export/hermes/wecom-node/package.json` | Node 清单 | 仅包含项目基础字段和占位测试脚本 |
| `channel-runtime-recovery-export/telegram/start_wecom_bridge.sh` | Shell 启动脚本 | 以后台 Node 进程启动 `wecom_bridge.mjs` |

### 5.2 原运行方式

- `bash start_wecom_bridge.sh`；或
- 在 `wecom-node` 目录直接执行 `node wecom_bridge.mjs`。

启动脚本通过 PID 文件和 `/proc/<pid>/cmdline` 判断进程是否已运行，并把输出写入日志。PID 和日志属于运行态数据，第一阶段不迁移。

### 5.3 依赖

| 依赖 | 审计结果 |
| --- | --- |
| Node.js | 必需；历史脚本直接调用 `node` |
| 企业微信 SDK | 源码 import `@wecom/aibot-node-sdk` |
| 清单缺口 | 恢复包中的 `package.json` 未声明上述 SDK，不能直接据此复现安装 |
| Node 内置模块 | `fs`、`path`、`crypto`、`child_process` |
| 外部调用 | Hermes 可执行入口和 `sn_agent_runner.py`；后者不在恢复包内 |

### 5.4 配置模板

源码识别出的配置键：

- `WECOM_BOT_ID`；
- `WECOM_BOT_SECRET`；
- `HERMES_HOME`；
- `SN_API_KEY` / `SENSENOVA_API_KEY`；
- `SN_BASE_URL`、`SN_CHAT_MODEL`。

实际 `.env` 已排除，恢复包中没有企业微信独立 `.env.example`。第一阶段 README 只记录键名和缺口，不创建或填充真实配置。

### 5.5 迁移目标

| 来源 | 目标 |
| --- | --- |
| `hermes/wecom-node/` | `plugins/wecom/recovered/wecom-node/` |
| `telegram/start_wecom_bridge.sh` | `plugins/wecom/recovered/start_wecom_bridge.sh` |
| 企业微信审计说明 | `plugins/wecom/README.md` |

启动脚本和 `wecom-node/` 在目标中保持原相对关系，使源码基线无需修改路径。

## 6. 微信客服（WeCom KF Gateway）

### 6.1 当前源码位置

| 恢复包位置 | 类型 | 说明 |
| --- | --- | --- |
| `channel-runtime-recovery-export/wecom/wecom_kf_gateway_v345.py` | Python Gateway | 1144 行历史生产版本 |
| `channel-runtime-recovery-export/wecom/healthcheck_v345.sh` | Shell 运维脚本 | 健康检查与无进程时启动逻辑 |
| `channel-runtime-recovery-export/docs/wecom-*.md` | 运行文档 | 蓝绿、SQLite 迁移、状态机等历史经验 |

### 6.2 原运行方式

- `bash healthcheck_v345.sh` 检查 `/healthz`；
- 无进程时以 `nohup python3 wecom_kf_gateway_v345.py` 启动；
- 历史服务端口为 `8798`；
- Gateway 使用 HTTP Server、消息同步轮询、SQLite 状态和外部 Agent runner。

### 6.3 依赖

| 依赖 | 审计结果 |
| --- | --- |
| Python 标准库 | HTTP Server、SQLite、XML、SSL、线程、subprocess、urllib 等 |
| 第三方 Python 包 | `pycryptodome`（`Crypto.Cipher.AES`）、Pillow（`PIL.Image`） |
| QwenPaw 调用 | QwenPaw CLI/可执行路径和 `sn_agent_runner.py` |
| 外部文件缺口 | `sn_agent_runner.py` 不在恢复包内 |
| 状态缺口 | 源码引用数据库和同步游标；ZIP 实际成员清单未包含数据库或游标文件 |

恢复报告提到历史数据库，但实际 ZIP 成员只有 Gateway、健康检查脚本和生成的探测图片。迁移以 ZIP 实际成员为准，不假设数据库可恢复。

### 6.4 配置模板

源码识别出的关键配置项：

- `CORP_ID`；
- `APP_SECRET`；
- `TOKEN`；
- `AESKEY` / `AES_KEY`；
- `OPEN_KFID`；
- `QWENPAW_BIN`；
- 数据库、日志、生成目录和同步游标路径。

实际 `.env` 已排除，恢复包没有微信客服 `.env.example`。第一阶段不从源码推导或生成密钥值。

### 6.5 迁移目标

| 来源 | 目标 |
| --- | --- |
| `wecom/wecom_kf_gateway_v345.py` | `plugins/wechat-customer/recovered/wecom_kf_gateway_v345.py` |
| `wecom/healthcheck_v345.sh` | `plugins/wechat-customer/recovered/healthcheck_v345.sh` |
| 相关 `docs/wecom-*.md` | `plugins/wechat-customer/docs/` |
| 微信客服审计说明 | `plugins/wechat-customer/README.md` |

`wecom/generated/` 中的历史探测图片不属于源码或文档，第一阶段不迁移。

## 7. WeChat MP Gateway

### 7.1 当前源码位置

| 恢复包位置 | 类型 | 说明 |
| --- | --- | --- |
| `channel-runtime-recovery-export/wechat/wechat_mp_gateway.py` | Python Gateway | 历史运行版本，端口 8799 |
| `channel-runtime-recovery-export/wechat/wechat_mp_gateway_v2.py` | Python Gateway | V2 候选，端口 8800 |

### 7.2 原运行方式

恢复报告记录的历史入口为：

```text
python3 wechat_mp_gateway.py
```

两个文件都实现基于 Python `ThreadingHTTPServer` 的回调服务。第一阶段保留两个版本，不判断或切换生产版本。

### 7.3 依赖

| 依赖 | 审计结果 |
| --- | --- |
| Python | 主要使用标准库：HTTP Server、XML、hashlib、subprocess、urllib、JSON |
| 外部 Agent | `QWENPAW` CLI；V2 还包含 `QWENPAW_API` 调用路径 |
| 启动脚本 | `NOT FOUND`；只有恢复报告中的直接 Python 启动方式 |

### 7.4 配置模板

识别出的配置项包括：

- `TOKEN`；
- `HOST`；
- `PORT`；
- `QWENPAW`；
- `QWENPAW_API`；
- `AGENT_TIMEOUT` / `QWENPAW_HTTP_TIMEOUT`。

恢复报告说明历史配置文件为 `mp-secret.env`，该文件已按敏感信息规则排除；ZIP 中没有脱敏模板。

### 7.5 迁移目标

| 来源 | 目标 |
| --- | --- |
| `wechat/wechat_mp_gateway.py` | `plugins/wechat-mp/recovered/wechat_mp_gateway.py` |
| `wechat/wechat_mp_gateway_v2.py` | `plugins/wechat-mp/recovered/wechat_mp_gateway_v2.py` |
| WeChat MP 审计说明 | `plugins/wechat-mp/README.md` |

## 8. Telegram Bridge

### 8.1 当前源码位置

| 恢复包位置 | 类型 | 说明 |
| --- | --- | --- |
| `channel-runtime-recovery-export/telegram/telegram_bridge.py` | Python Bridge | 历史实现之一，包含 Unix 文件锁 |
| `channel-runtime-recovery-export/telegram/telegram_bridge_main.py` | Python Bridge | 恢复报告标记的主程序 |
| `channel-runtime-recovery-export/telegram/start_bridge.sh` | Shell 启动脚本 | 后台启动、日志和 PID 管理 |
| `channel-runtime-recovery-export/telegram/telegram_bridge.pid` | 运行态文件 | 禁止迁移 |

### 8.2 原运行方式

- `bash start_bridge.sh`；
- 脚本向 `telegram_bridge_main.py` 传递 `HERMES_HOME`；
- Bridge 通过 Telegram HTTP API 轮询消息，再调用 Hermes/Agent runner；
- 输出写入日志，PID 写入 PID 文件。

### 8.3 依赖

| 依赖 | 审计结果 |
| --- | --- |
| Python | 以标准库为主：urllib、subprocess、JSON、pathlib、time |
| 平台限制 | `telegram_bridge.py` 使用 `fcntl`，属于 Unix/Linux 依赖 |
| Hermes | `HERMES_HOME` 和 `run_image_and_reply.sh` |
| 外部运行文件 | `run_image_and_reply.sh` 存在，但它继续调用的外部 Python runner 未包含 |
| 网络 | Telegram Bot HTTP API；第一阶段不连接 |

### 8.4 配置模板

源码识别出的配置键：

- `TELEGRAM_BOT_TOKEN`；
- `TELEGRAM_ALLOWED_USERS`；
- `HERMES_HOME`；
- State、offset、日志与 lock 文件路径。

实际 `.env` 已排除，恢复包没有 Telegram `.env.example`。第一阶段 README 只记录键名，不恢复真实值。

### 8.5 迁移目标

| 来源 | 目标 |
| --- | --- |
| `telegram/telegram_bridge.py` | `adapters/telegram/recovered/telegram_bridge.py` |
| `telegram/telegram_bridge_main.py` | `adapters/telegram/recovered/telegram_bridge_main.py` |
| `telegram/start_bridge.sh` | `adapters/telegram/recovered/start_bridge.sh` |
| Telegram 审计说明 | `adapters/telegram/README.md` |

## 9. 第一阶段迁移清单

### 9.1 允许迁移

- 上述 Python、JavaScript/MJS、Shell 源码；
- Hermes 工程内的源码、测试、许可和已有文档；
- 已有 `.env.example`、`*.yaml.example` 和 Docker/Nix 配置；
- 恢复报告与 Channel 运行文档；
- 每个目标目录的来源、校验值和缺口说明。

### 9.2 禁止迁移

- `.env`、token、secret、API key、credentials；
- `*.pid`、`*.log`；
- `hermes-agent-main/log.txt` 等历史运行日志；
- SQLite/DB、同步游标、session、memory 和用户消息；
- `wecom/generated/` 探测图片；
- 缓存、构建产物、`node_modules`、虚拟环境；
- 任何来自当前 Runtime 的运行状态。

### 9.3 原样性要求

1. 从 ZIP 复制后生成逐文件 SHA-256 清单；
2. `recovered/` 中的来源文件必须与 ZIP 成员字节一致；
3. 不格式化、不修 import、不改绝对路径；
4. 不把恢复源码接入 `core/contracts` 或现有 Channel；
5. 只用 README 记录依赖缺口和后续工作；
6. 在独立提交中完成源码基线迁移，便于整体回滚。

## 10. 后续阶段（不在本次范围）

| 阶段 | 内容 | 前置条件 |
| --- | --- | --- |
| Phase 2 | 补齐可复现依赖清单和脱敏配置模板 | Phase 1 字节级基线已锁定 |
| Phase 3 | 用 Extension Contract 包装历史入口 | 不修改 `recovered/` 源码 |
| Phase 4 | 离线 Fake Client/协议回归 | 配置和外部调用均可替换 |
| Phase 5 | Cloud staging 恢复验证 | 用户明确授权访问 staging |
| Phase 6 | Runtime/Channel 接入评审 | 单独方案、单独授权、可回滚 |

## 11. 验收与回滚

第一阶段验收条件：

- 迁移目标与本计划映射一致；
- 逐文件 SHA-256 与恢复包成员一致；
- 没有敏感文件和运行态数据进入 Git；
- 没有修改现有 Agent、Runtime、Channel、PDF Editor；
- 没有新增网络连接或启动脚本执行；
- Git 提交只包含恢复源码、已有文档、脱敏示例和清单。

回滚方式：整体回退第一阶段源码迁移提交。由于该阶段不接入 Runtime，也不修改原业务逻辑，回滚不影响现有运行能力。
