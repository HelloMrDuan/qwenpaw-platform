# QwenPaw 企业扩展架构

## 1. 目标与边界

本规范定义 `qwenpaw-platform` 作为企业 Extension/Workspace 仓库时的扩展分类、目录、开发流程和版本管理规则。

QwenPaw/AgentScope Runtime 继续由官方部署提供。本仓库不复制或修改 Runtime 内核；扩展通过官方 Skill、Plugin、MCP 接口，或平台自有 Adapter 与 Runtime 协作。

本规范是目标架构。现有目录和能力采用渐进迁移，不在建立规范时批量搬迁或改写。

## 2. 扩展类型分类

### 2.1 Skill

Skill 表达一个由 Agent 选择和执行的用户能力或工作流。

适用范围：

- 文件处理；
- AI 能力编排；
- 工具调用流程；
- 有明确输入、输出或文件制品的任务；
- 需要通过 `SKILL.md` 告诉 Agent 何时使用、如何执行和如何验收的能力。

当前示例：

- `pdf-editor`：确定性 PDF 修改与验证；
- `docx`：Word 文档处理；
- `xlsx`：Excel 文件处理；
- `pptx`、`pdf`、`file_reader`。

Skill 不应：

- 注册 Runtime 生命周期 Hook；
- 修改 AgentScope 推理循环；
- 直接实现 Telegram、企业微信等 Channel 传输；
- 把 Provider 凭据写入源码；
- 依赖未记录的云端绝对路径或全局包。

### 2.2 Plugin

Plugin 是由 QwenPaw Runtime 加载的高权限扩展，可增强 Runtime 或注册新的系统级能力。

适用范围：

- Runtime 增强；
- 外部服务的深度集成；
- 新 Provider、Middleware、Hook、命令、HTTP API 或前端能力；
- 新 Channel 的注册和生命周期管理；
- 需要在应用启动、关闭或 Agent 推理阶段运行的逻辑。

示例：

- 企业微信 Channel Plugin；
- Telegram Channel Plugin；
- 第三方模型或企业服务 Provider Plugin；
- 审计、Tracing、企业权限 Middleware Plugin。

Plugin 与 Runtime 共享进程或高信任边界，必须固定 QwenPaw 兼容版本，进行安全评审和独立回滚。单纯的用户任务不应升级成 Plugin。

### 2.3 Adapter

Adapter 是平台自有的协议或数据模型转换层，本身通常不是 Runtime 可独立安装的扩展。

适用范围：

- 协议转换；
- Channel 原始消息与平台标准消息之间的转换；
- 外部错误、附件、身份和会话标识的标准化；
- 对官方 Runtime 接口的薄兼容封装。

示例：

- Telegram Update → Normalized Message；
- 企业微信事件 → Normalized Message；
- Response Event → Channel 文本、卡片或文件消息；
- Provider/MCP 错误 → 平台标准错误。

Adapter 应保持纯转换、无业务决策、可离线测试。新 Channel 通常由一个 Plugin 负责注册和生命周期，由一个或多个 Adapter 负责消息转换。

### 2.4 MCP

MCP 扩展通过 Model Context Protocol 向 Agent 暴露外部工具。

适用范围：

- 搜索；
- 数据库查询；
- 企业或第三方 API；
- 可被多个 Agent/Skill 复用的外部工具；
- 已有 MCP Server 或适合独立进程、网络服务运行的能力。

示例：

- Tavily 搜索；
- 企业知识库查询；
- 只读数据库工具；
- CRM、ERP、工单或内部 API Gateway。

MCP Server 负责工具 schema 和执行；Skill 可以编排 MCP 工具，但不应复制 MCP Server 的连接实现。凭据通过 Runtime Secret/credential reference 注入。

## 3. 四类扩展的关系

```text
User request
    ↓
Skill：定义任务、步骤和交付物
    ↓ optional tool call
MCP：提供外部工具协议与执行

Channel payload
    ↓
Plugin：注册 Channel、管理连接和生命周期
    ↓
Adapter：转换消息、附件、错误和响应事件
    ↓
QwenPaw Runtime
```

一个企业能力可以由多种扩展组合，但每一层只承担自己的责任：

- “用企业数据库生成 Excel 报告”＝数据库 MCP + XLSX Skill；
- “在企业微信中使用该报告”＝企业微信 Plugin + 消息/附件 Adapter；
- “模型调用全链路审计”＝Runtime Middleware Plugin，而不是 Skill；
- “把供应商错误映射成统一错误”＝Adapter，而不是 Plugin 中散落的业务判断。

## 4. 目标目录规范

最终核心结构：

```text
qwenpaw-platform/
├── skills/
├── plugins/
├── adapters/
├── mcp/
├── configs/
├── tests/
└── docs/
```

目录责任：

| 目录 | 责任 |
| --- | --- |
| `skills/` | Agent 可选择的用户能力、工作流和文件处理能力 |
| `plugins/` | QwenPaw Runtime Plugin 源码与发布清单 |
| `adapters/` | Channel、Runtime、Tool 的纯协议转换和兼容层 |
| `mcp/` | MCP Server 源码、Driver 声明、schema 和部署说明 |
| `configs/` | 非敏感配置、schema、示例和环境 overlay |
| `tests/` | 跨 Extension 契约、集成、回归和 Cloud staging fixture |
| `docs/` | 架构、决策、开发、发布、恢复和运维文档 |

当前 `drivers/mcp/`、`channels/`、`apps/`、`core/` 不在本阶段移动或删除。迁移时逐个 Extension 建立新目录、兼容入口和回滚路径。

## 5. 单个扩展目录规范

### Skill

```text
skills/<skill-id>/
├── SKILL.md
├── skill.yaml              # 目标仓库 manifest；需保留 Runtime 兼容入口
├── README.md
├── CHANGELOG.md
├── schemas/
├── executor/               # 或小型 Skill 的 executor.py
└── tests/
```

现有 Skill 继续以 `SKILL.md` 为实际兼容入口。不得因为增加目标 manifest 而宣称当前 Runtime 已原生支持 `skill.yaml`。

### Plugin

```text
plugins/<plugin-id>/
├── plugin.json             # QwenPaw Plugin manifest 与版本
├── plugin.py               # 或 manifest 声明的入口
├── README.md
├── CHANGELOG.md
├── requirements.txt        # 如需要，必须锁定或有上层 lock
├── src/
└── tests/
```

Plugin 必须声明兼容的 QwenPaw 最低/最高版本、权限、依赖和注册能力。前端 Plugin 还需拥有独立 Node manifest/lock 和构建验证。

### Adapter

```text
adapters/<adapter-id>/
├── adapter.yaml
├── README.md
├── CHANGELOG.md
├── src/
├── schemas/
├── fixtures/
└── tests/
```

`adapter.yaml` 至少声明 id、version、输入协议、输出协议和兼容 schema 版本。Adapter 不拥有凭据和外部连接生命周期。

### MCP

```text
mcp/<mcp-id>/
├── mcp.yaml
├── README.md
├── CHANGELOG.md
├── server/                 # 自研 MCP Server 时使用
├── schemas/
├── tests/
└── deploy/
```

`mcp.yaml` 声明版本、transport、命令/endpoint、工具清单、权限和 credential reference。外部 npm/Python Server 必须使用精确版本，禁止 `@latest` 进入生产发布基线。

## 6. 开发流程

```text
需求
  ↓
判断扩展类型
  ↓
创建或修改单个 Extension
  ↓
本地测试
  ↓
Cloud staging
  ↓
版本化发布
```

### 6.1 需求

- 定义用户价值、触发方式、输入、输出、制品和失败模式；
- 确认是否需要外部网络、凭据、持久化或 Runtime 生命周期能力；
- 明确现有 Extension 能否满足，避免重复建设。

### 6.2 判断类型

使用 `docs/EXTENSION_DECISION_GUIDE.md` 完成分类。跨类型需求拆成独立发布单元，不创建同时承担 Skill、Channel 和 Provider 责任的单体 Extension。

### 6.3 创建 Extension

- 一个分支只处理一个主 Extension；
- 创建 README、CHANGELOG、manifest 和 tests；
- 复用公共 schema，不复制 Runtime 内部实现；
- 新增依赖必须锁定，新增 Secret 只能声明引用名称。

### 6.4 本地测试

- Manifest/schema 静态检查；
- 单元测试与脱敏 fixture；
- Skill/Adapter/MCP 的离线契约测试；
- Plugin 的注册、权限和生命周期测试；
- 文件制品结构与渲染验证；
- 不启动或模拟一个自制 QwenPaw Runtime 来替代官方集成测试。

### 6.5 Cloud staging

- 使用固定版本的官方 QwenPaw Runtime；
- 使用非生产 Workspace、测试账号和测试凭据；
- 验证发现、加载、权限、错误、超时、制品和卸载/回滚；
- 记录 Runtime 版本、Extension 版本、commit、配置快照和测试结果；
- 外部 Channel 未通过端到端测试前保持禁用。

### 6.6 发布

- 从干净 commit 构建不可变 bundle；
- 生成 SHA-256、依赖清单和兼容矩阵；
- 通过官方 Skill/Plugin/MCP 安装机制发布；
- 先 staging，后生产；
- 保留上一版本制品和配置，确保无需修改 Runtime 即可回滚。

## 7. 版本管理

每个 Extension 必须独立版本化，不使用仓库 commit 代替 Extension 版本。

最低要求：

- 独立版本号；
- `CHANGELOG.md`；
- `README.md`；
- 自动化测试；
- Runtime/schema 兼容范围；
- 发布制品 SHA-256；
- 明确的上一可回滚版本。

### 7.1 语义化版本

- Patch：不改变公开契约的修复；
- Minor：向后兼容的新能力；
- Major：输入、输出、协议、权限或行为不兼容。

### 7.2 Tag 规范

建议按扩展类型和 id 创建 tag：

```text
skill/pdf-editor/v1.1.0
plugin/wecom-channel/v1.0.0
adapter/channel-message/v1.0.0
mcp/tavily-search/v1.0.0
```

同一提交可以包含多个 Extension，但发布 tag、bundle、CHANGELOG 和兼容矩阵必须分别生成。生产配置只引用已发布版本，不引用分支或 `latest`。

### 7.3 CHANGELOG 要求

每个版本至少记录：

- Added、Changed、Fixed、Security 中适用的条目；
- 输入输出或配置兼容性；
- 新增/删除依赖；
- 数据或文件格式迁移；
- 升级步骤与回滚限制。

## 8. 测试与安全门禁

| Extension | 最低测试门禁 |
| --- | --- |
| Skill | 触发契约、输入输出、文件安全、制品验证、失败与依赖缺失 |
| Plugin | manifest、兼容版本、注册/卸载、权限、生命周期、安全审查 |
| Adapter | 双向映射、未知字段、附件、错误、幂等和回放 fixture |
| MCP | tool schema、协议握手、超时、取消、权限、凭据脱敏和 Server 失败 |

通用安全要求：

- Secrets 不进入 Git、bundle、日志或 fixture；
- Extension 使用最小文件、网络和工具权限；
- Plugin 按高权限代码审查；
- 数据库 MCP 默认只读，写操作需要独立审批和审计；
- Channel Adapter 不保存 Provider 原始凭据；
- 发布前必须验证卸载或回滚路径。

## 9. 渐进迁移规则

| 当前内容 | 目标位置 | 规则 |
| --- | --- | --- |
| `skills/*` | `skills/*` | 保持原路径，逐个补齐版本、README、CHANGELOG 和测试 |
| `drivers/mcp/tavily_search.yaml` | 未来 `mcp/tavily-search/` | 先建立兼容包和精确版本，再切换配置；当前文件不移动 |
| `channels/` 占位目录 | `plugins/<channel>/` + `adapters/<channel>/` | Plugin 管生命周期，Adapter 管转换；恢复源码后逐渠道迁移 |
| `scripts/` 外部 Gateway 运维脚本 | 对应 Plugin 的 `deploy/` 或独立运维目录 | 只有恢复所有者源码并完成验收后才移动 |
| `configs/` | `configs/` | 保持 Runtime 兼容，Secrets 继续忽略 |
| `tests/` | `tests/` + Extension 自身 `tests/` | 平台契约放根 tests，Extension 专属测试就近放置 |

禁止一次性搬迁、删除旧入口或为了目录整齐修改业务行为。每次迁移只处理一个可独立测试和回滚的 Extension。
