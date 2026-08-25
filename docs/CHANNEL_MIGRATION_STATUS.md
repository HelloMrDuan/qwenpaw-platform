# Channel Migration Status

## 1. 结论

Telegram、企业微信、微信客服与 Hermes 已由用户确认在 QwenPaw/AgentScope 云端环境完成过运行验证；本报告不否定该历史事实。但当前 Git 仓库和 `qwenpaw-platform-export.zip` 是 Workspace/Extension 资产快照，不包含这些 Channel 的完整可执行实现。

本次审计结论：

- 不应立即重新开发 Telegram、WeCom 或 WeChat Adapter；
- 应先从原云端 Runtime 版本、外部 NAS、容器镜像、部署制品或其他备份恢复原实现；
- `configs/agent.json` 中的 Channel 配置可作为恢复同版本 QwenPaw Runtime 的配置依据，但不能当作 Adapter 源码；
- WeCom 客服 Gateway 的脚本与 runbook 可迁移为运维资产，但不足以形成可发布 Extension；
- Hermes、WeCom 客服 Gateway 和微信公众平台 Gateway 属于“有外部运行证据、仓库无实现”的恢复优先项。

## 2. 状态定义

| 状态 | 定义 |
| --- | --- |
| `AVAILABLE` | 源码、非敏感配置模板、启动入口和最低测试证据均存在，可直接进入 Extension 迁移 |
| `CONFIG_ONLY` | 仓库只有 Runtime 配置/schema，Channel Loader 或 Adapter 实现不在仓库 |
| `RUNTIME_ONLY` | 有云端/外部运行、健康检查或部署记录，但完整源码与可发布制品不在仓库 |
| `MISSING` | 未找到配置、源码、入口、制品或可信运行证据 |

状态表示“当前仓库中的迁移资产完整度”，不是对历史云端能力是否运行过的判断。

## 3. 扫描范围与安全边界

已检查：

- `configs/` 的文件名和 `agent.json` Channel 键结构；
- `scripts/`、`drivers/`、`channels/`；
- `digest/` 中 Channel 运维知识；
- 历史 `memory/` 文件名及非敏感实现文件引用；
- `qwenpaw-platform-export.zip` 的 377 个成员名称和非敏感资产类型。

未读取、未复制、未输出：

- `configs/credentials.yaml` 的内容；
- 任何 bot token、secret、password、Authorization header 或签名材料；
- `chats.json`、session 内容、用户消息或生产数据库内容；
- 下载链接、Webhook 验证值和真实账号标识。

配置键存在只用于确认 schema；所有实际凭据仍应由 Secret Manager 或受控部署环境注入，禁止迁入 Git。

## 4. 资产总览

| 名称 | 主状态 | 历史运行方式 | 源码 | 配置 | 启动/Webhook/Gateway 资产 | 迁移判断 |
| --- | --- | --- | --- | --- | --- | --- |
| Telegram | `CONFIG_ONLY` | QwenPaw Cloud Runtime 内置 Channel；用户确认曾验证运行 | 不存在 | `channels.telegram` 存在，导出快照 `enabled=false` | 无 Telegram 启动脚本、Webhook、Gateway 或 Adapter；Hermes 的关系无法从快照证明 | 同版本 Runtime 可先恢复配置；Extension 源码不能直接迁移 |
| 企业微信内置 Channel | `CONFIG_ONLY` | QwenPaw Cloud Runtime 的 `channels.wecom`；用户确认曾验证运行 | 不存在 | `channels.wecom` 存在，导出快照 `enabled=false` | 无仓库内 Channel Loader/Adapter | 同版本 Runtime 可恢复配置；不要用客服 Gateway 代码替代内置 Channel |
| 企业微信/微信客服 Gateway | `RUNTIME_ONLY` | 外部 `wecom-kf` Python Gateway，callback + polling、SQLite、Funnel、客服 API | 真实 Gateway `.py` 不存在 | 凭据文件存在但未检查；运行配置主要在外部环境 | 两个健康/清理脚本、多个 runbook、历史部署文件名与外部路径引用 | 先恢复外部源码、数据库 schema 与部署制品；当前不能直接发布 |
| WeChat 内置 Channel | `CONFIG_ONLY` | QwenPaw Cloud Runtime 的 `channels.wechat`；用户确认相关微信能力曾验证 | 不存在 | `channels.wechat` 存在，导出快照 `enabled=false` | 无仓库内 Adapter；只看到 token/base URL/message merge 等键名 | 只适合同版本 Runtime 配置恢复，不足以形成 Extension |
| 微信公众号/微信机器人 Gateway | `RUNTIME_ONLY` | 外部 callback/XML/被动回复 Gateway，经 HTTPS/Funnel 接入 QwenPaw | 不存在 | 外部 callback 配置未导出；不得与 `channels.wechat` 自动等同 | 有 API 陷阱/被动回复 runbook，无 Gateway 源码和 fixture | 先恢复原 Gateway；找不到后才评估重实现 |
| Hermes Bridge | `RUNTIME_ONLY` | Heartbeat 调用外部 `hermes/start_bridge.sh` | 不存在 | `agent.json` 无 `channels.hermes`；未找到独立 Hermes 配置模板 | 只有外部启动入口和历史健康检查描述 | 必须恢复 Hermes 包、协议、版本和启动资产，不能仅凭脚本名重写 |

当前 `channels/` 只有 `.gitkeep`；`drivers/` 只有 Tavily MCP 和旧 MCP 迁移报告，不包含上述 Channel Driver。

## 5. Telegram

### 已有资产

- `configs/agent.json` 包含 `channels.telegram` 配置结构；
- 键名覆盖启用开关、Bot 凭据引用、API base URL、HTTP proxy、访问控制、Tool 展示和 streaming 开关；
- 用户确认 Telegram 已在原 QwenPaw/AgentScope 云端环境验证运行。

### 未找到

- Telegram Adapter/Plugin 源码；
- polling/webhook 启动入口；
- Telegram 专用脚本、fixture、自动测试或发布包；
- 可以证明 Hermes 与 Telegram 具体协议关系的源码或清单。

### 迁移缺口

1. 原 QwenPaw Runtime 精确版本和内置 Telegram Channel Loader；
2. 非敏感配置 overlay 与 Secret 注入映射；
3. Update JSON、回复、文件、限流和 streaming 行为 fixture；
4. staging Bot 的发送/编辑/文件回归证据；
5. 若原能力实际经 Hermes 转发，需要恢复 Hermes 协议和版本后再决定边界。

### 判断

当前为 `CONFIG_ONLY`。如果目标环境继续使用相同官方 Runtime，优先恢复配置并做 staging 验证，不应先重写 Telegram Adapter。只有确认官方/原 Hermes 实现不可恢复且 Extension 层确有独立托管需求时，才进入新 Adapter 设计。

## 6. 企业微信内置 Channel

### 已有资产

- `configs/agent.json` 包含 `channels.wecom` 配置结构；
- 键名覆盖 bot ID、secret 引用、WebSocket URL、欢迎消息、重连、共享 session 和 streaming；
- 用户确认企业微信能力曾在云端验证。

### 未找到

- 内置 WeCom Channel Loader 或 Adapter 源码；
- 独立启动脚本、WebSocket 客户端实现、fixture 和自动测试。

### 判断

当前为 `CONFIG_ONLY`。它属于 QwenPaw Runtime 能力恢复问题；应先锁定原 Runtime 版本并恢复非敏感配置。不要把外部 `wecom-kf` 客服 Gateway 当作同一个实现直接迁移。

## 7. 企业微信/微信客服 Gateway

### 已有资产

- `scripts/cleanup_old_gateways.sh`：识别历史 V3.4.1–V3.4.4 进程并检查 V3.4.5；
- `scripts/healthcheck_v345_final.sh`：引用外部 `wecom_kf_gateway_v345.py` 并执行健康检查/缺失进程恢复；
- `configs/HEARTBEAT.md`：调用外部 `wecom-kf` 健康检查；
- `digest/`：记录蓝绿切换、callback/polling 兜底、SQLite 状态机、图片上传和客服 API 陷阱；
- 历史 memory 文件引用 V3.4–V3.4.5 Gateway、`gateway-v32.db`、cursor JSON 和 `sn_agent_runner.py`；
- 用户确认相关企业微信/微信客服链路曾在云端验证。

### 未找到

- `wecom_kf_gateway_v*.py` 实际源码；
- SQLite 初始化/迁移程序和 schema 文件；
- callback 路由实现、签名/解密实现、客服 API Client；
- 部署 manifest、锁定依赖、systemd/container 定义；
- 脱敏 fixture、自动测试和可回滚发布包。

### 判断

当前为 `RUNTIME_ONLY`。两个 shell 文件是外部服务的运维入口，不是 Gateway 本身；runbook 是恢复证据，不是可执行源码。优先从原 NAS、实例磁盘、容器镜像、云端部署制品或更完整 backup 恢复 V3.4.5 及其数据库 schema，再迁入 `plugins/` + `adapters/`。只有恢复渠道全部失败后，才依据协议和 runbook 重新实现。

## 8. WeChat 与微信公众平台 Gateway

必须区分三种容易混淆的能力：

1. QwenPaw `channels.wechat` 内置 Channel；
2. 企业微信“微信客服” API Gateway（上一节的 `wecom-kf`）；
3. 微信公众号/微信机器人 callback Gateway。

它们的协议、凭据和生命周期不同，不能因为都叫“微信”就共用 Adapter。

### 已有资产

- `channels.wechat` 配置结构包含 token 引用、base URL 和 message merge 参数，导出快照为禁用；
- `digest/wiki/wechat-mp-48001-passive-reply-bypass.md` 记录公众号被动回复与 Gateway 规避经验；
- WeCom 客服 runbook 记录客服消息同步、发送和媒体上传；
- 用户确认微信机器人/微信客服曾在云端验证。

### 未找到

- 微信内置 Adapter 源码；
- 公众号 callback/XML Gateway 源码；
- 签名验证、加解密、Webhook fixture 和端到端测试；
- 可确认“微信机器人”具体对应哪一种实现的部署 manifest。

### 判断

内置 `channels.wechat` 为 `CONFIG_ONLY`；历史公众号/客服 Gateway 为 `RUNTIME_ONLY`。下一步必须先做实例身份确认和源码恢复，不能直接创建一个泛化 `wechat adapter`。

## 9. Hermes

### 已有资产

- `configs/HEARTBEAT.md` 记录外部 `hermes/start_bridge.sh` 启动/健康入口；
- 现有状态文档将 Hermes 描述为外部 Bridge/Plugin/Adapter 能力；
- 用户确认 Hermes 在原云端环境实际存在。

### 未找到

- Hermes 源码、二进制、包版本或依赖清单；
- 消息协议、Channel 映射、配置 schema 和凭据模板；
- Telegram/WeCom/WeChat 与 Hermes 的确切连接关系；
- fixture、测试和发布/回滚制品。

### 判断

当前为 `RUNTIME_ONLY`。`start_bridge.sh` 只存在于外部路径，导出包中没有该脚本本体。应先从原运行环境恢复整个 Hermes 目录与版本元数据；不得根据一个启动脚本路径推测并重写其协议。

## 10. 历史导出包结论

`qwenpaw-platform-export.zip`：

- 共有 377 个成员；
- 包含 `configs/agent.json` 和未读取内容的 `configs/credentials.yaml`；
- 包含与当前仓库一致的 WeCom 清理/健康检查脚本；
- 包含 WeCom/WeChat runbook 和历史 memory 文档；
- 没有以 Telegram、WeCom、WeChat 或 Hermes 命名的 Adapter/Gateway `.py`、`.js`、`.ts`、service 或部署配置；
- 没有 `hermes/start_bridge.sh`、`wecom_kf_gateway_v345.py` 或微信公众平台 Gateway 源码。

因此该 ZIP 不是 Channel 全量部署备份，不能从中直接还原原云端 Channel Runtime。

## 11. 下一步方案

### 可以直接迁移

- WeCom/WeChat 的 `digest/` runbook 可迁入长期运维知识体系；
- 两个 WeCom shell 脚本可作为“外部服务恢复入口参考”保留，但在外部路径参数化和安全审查前不能当作 Production Extension 发布；
- `agent.json` 的 Channel 键结构可提炼为不含值的配置 schema/overlay 模板。

当前没有一个 Telegram、WeCom、WeChat 或 Hermes 实现满足 `AVAILABLE`，因此没有完整 Channel Adapter 可以直接代码迁移。

### 只需要恢复配置的条件

当且仅当目标环境恢复了与原云端一致的 QwenPaw/AgentScope Runtime 和内置 Channel Loader 时：

- Telegram 可恢复 `channels.telegram` 非敏感 overlay；
- 企业微信内置 Channel 可恢复 `channels.wecom` overlay；
- WeChat 内置 Channel 可恢复 `channels.wechat` overlay；
- 凭据必须从 Secret Manager/受控环境重新注入，不能复制进 Git；
- 恢复后仍需 staging 回归，不能依据 `enabled=true` 判定成功。

### 需要先恢复源码、恢复失败后才重实现

- Hermes Bridge；
- 企业微信/微信客服 `wecom-kf` Gateway；
- 微信公众号/微信机器人 callback Gateway；
- 任何未包含在目标 QwenPaw Runtime 版本中的 Telegram/WeCom/WeChat 私有 Adapter。

### 推荐执行顺序

1. 锁定原 QwenPaw/AgentScope Runtime、Hermes 和 Gateway 版本/镜像摘要；
2. 从 NAS、实例磁盘、镜像层、发布制品和额外 backup 搜索缺失源码；
3. 对恢复文件做 secret 隔离、许可证和依赖扫描；
4. 为每个实现建立独立 Extension inventory：源码、配置模板、入口、依赖、状态存储、测试、回滚；
5. 使用现有 Message/Stream/Renderer Contract 编写兼容 Adapter，不修改恢复的 Runtime 核心；
6. 在 Cloud staging 使用测试账号完成 callback、收发、文件、重连、限流和回滚验收；
7. 只有原实现确定不可恢复时，单独立项重新实现相应 Adapter/Gateway。

本阶段没有创建 Telegram、WeCom 或 WeChat Adapter，也没有修改 Runtime、Agent、PDF、Console Adapter 或任何已有 Skill。
