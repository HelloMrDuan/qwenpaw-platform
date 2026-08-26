# QwenPaw Platform Deployment Model

## 1. 模型目标

`qwenpaw-platform` 是 Extension/Workspace 的开发源仓库，不是 QwenPaw Runtime 本体。

Channel deployment override: QwenPaw v2.1.0 built-in Telegram、企业微信和微信
Channels are the production default. Repository Telegram/WeCom Adapters,
Plugins, and Bridges are `LEGACY / FALLBACK / REFERENCE ONLY` and must not be
deployed as replacements. WeChat Customer remains `CUSTOM / TO VERIFY`; PDF
Editor remains a custom Skill. See `QWENPAW_CHANNEL_STRATEGY.md`.

部署链路：

```text
Local Development Repository
        ↓ test / validate / package
Immutable Release Package
        ↓ staging install / restore
AgentScope/QwenPaw Workspace + Runtime Extension
        ↓ acceptance
Production Runtime
```

仓库不重写 AgentScope/QwenPaw Runtime，也不把本地 Extension 代码直接覆盖到运行实例。

## 2. Git 仓库角色

Git 保存：

- Skills、Plugin、Adapter 和 MCP 的开发源；
- Extension Contract 与离线测试；
- 脱敏配置模板和 schema；
- 架构、发布、迁移与回滚文档；
- Release manifest 和 checksum。

Git 不保存：

- Runtime 本体；
- `.env`、secret、credentials；
- memory、session、聊天记录；
- 运行数据库、cursor、PID、日志；
- 临时上传包和云端运行状态。

## 3. Skill 部署

```text
skills/<skill>/
        ↓ validate contract and tests
Skill Release Package
        ↓ upload / restore
AgentScope Workspace skills/
```

发布要求：

- `skill.yaml`、README、schema、executor 和测试完整；
- 版本与 CHANGELOG 明确；
- Release Package 不包含测试数据中的敏感文件；
- 在 staging Workspace 验证 Skill 发现、加载、调用和 Artifact；
- 生产发布前保留上一版本包用于回滚。

Skill 只进入 Workspace Skill 目录，不修改 Runtime 核心。

## 4. Plugin 部署

```text
plugins/<plugin>/
        ↓ dependency lock / offline tests
Plugin Release Package
        ↓ Runtime-supported installation
Runtime Extension
```

Plugin Package 应包含：

- Plugin metadata、版本和兼容 Runtime 范围；
- 入口与生命周期说明；
- 锁定的 Python/Node 依赖；
- config schema 与 `.env.example`；
- healthcheck、测试和回滚说明；
- 来源与 license。

`plugins/*/recovered/` 只是历史来源基线。只有在其外部建立包装层、测试并满足 Runtime Extension 接口后，才能构建可安装 Plugin。

具体安装命令取决于目标 QwenPaw Runtime 版本支持的 Extension 机制；发布流程不得假设可直接复制文件到 Runtime 内部目录。

## 5. Adapter 部署

Adapter 负责 Channel 协议与统一 Message/Streaming Contract 的转换。

部署形态分为：

1. Runtime 原生支持的 Adapter：以 Runtime 允许的 Extension 方式安装；
2. 外部进程 Adapter：作为独立服务部署，通过已批准的 API/队列/协议连接 Runtime；
3. 历史 Bridge：先保存在 `recovered/`，完成包装和离线测试前不得部署。

Adapter Release Package 必须声明：

- 输入 Channel 协议；
- MessageEvent 映射；
- StreamEvent/RenderedOutput 策略；
- 重试、幂等、限流和 healthcheck；
- secret 与网络权限；
- Runtime 连接方式和回滚方式。

## 6. 配置迁移与 Secret 注入

```text
config template / schema in Git
        +
secret from deployment environment
        ↓ render at deploy time
runtime configuration
```

规则：

- Git 只保存 `.env.example`、JSON/YAML template 和 schema；
- token、secret、API key 从云端 Secret Manager、CI/CD Secret 或人工批准的安全渠道注入；
- Release Package 不携带生产 secret；
- 配置模板必须区分 required、optional、default 和 sensitive；
- 环境差异通过 overlay 管理，不直接编辑生产模板；
- 部署前检查旧配置兼容性，部署后只验证键是否生效，不输出值。

Agent 配置迁移必须单独评审。Extension 发布不得顺带覆盖 `agent.json`、memory 或 session。

## 7. Release Package

Release Package 是从 Git commit 构建的运行制品，不是源码目录的临时 ZIP。

建议结构：

```text
release/
├── manifest.yaml
├── payload/
├── config/
│   └── *.example
├── checksums.sha256
├── LICENSES/
├── README.md
└── ROLLBACK.md
```

Manifest 至少记录：

- Extension 名称、类型、版本；
- Git commit；
- Runtime/Workspace 兼容范围；
- 入口和依赖；
- 配置 schema 版本；
- 数据迁移要求；
- healthcheck；
- 前一稳定版本和回滚步骤。

Release Package 必须不可变。同一版本不得覆盖重发；修订必须提升版本。

## 8. AgentScope/QwenPaw 恢复流程

建议恢复顺序：

1. 确认目标 Runtime 版本与 Extension 兼容范围；
2. 对当前 Workspace 执行官方支持的 Backup；
3. 在隔离环境 Restore Workspace 基线；
4. 验证 configs、skills、memory 结构和 Agent 配置；
5. 逐个安装经过验证的 Skill Release Package；
6. 逐个安装 Runtime 支持的 Plugin/Adapter Package；
7. 从安全系统注入 secret；
8. 执行离线/healthcheck/Channel staging 验收；
9. 保存发布 manifest、checksum 和恢复点；
10. 经批准后切换生产流量。

若目标 Runtime 不支持某类 Extension 安装，应停止发布并选择外部服务部署或等待接口支持，不能修改 Runtime 核心绕过限制。

## 9. 本地开发、测试与发布边界

| 阶段 | 允许 | 禁止 |
| --- | --- | --- |
| 本地开发 | 修改包装层、schema、tests、README | 使用生产 secret、写云端状态 |
| 离线测试 | Fake Client、Contract、事件顺序、Artifact | 连接真实 Channel 或生产 Runtime |
| Staging | 使用独立测试账号、验证安装和回滚 | 复用生产 token/数据库 |
| Release | 从干净 commit 构建并签名/checksum | 手工修改已构建包 |
| Production | 安装已审批制品、注入 secret、执行 healthcheck | 在线修改源码或覆盖 Runtime 核心 |

## 10. 发布与回滚责任边界

仓库负责：

- 代码与文档质量；
- dependency lock；
- 配置 schema；
- 离线测试；
- Release Package 与 checksum；
- 迁移/回滚说明。

部署环境负责：

- Runtime 可用性与兼容接口；
- secret 注入；
- 网络、证书和域名；
- 数据库/状态一致性备份；
- staging 和生产审批；
- 监控、告警和流量切换。

回滚优先恢复上一不可变 Release Package；涉及数据库时必须使用部署前一致性恢复点。不得通过修改 Agent、Runtime 或历史 `recovered/` 源码临时回滚。
