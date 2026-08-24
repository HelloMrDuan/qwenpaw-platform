# QwenPaw Extension 类型决策指南

## 1. 快速决策

依次回答以下问题，命中后停止：

```text
1. 是否必须介入 Runtime 启停、Agent 推理、Provider、命令、HTTP/前端或 Channel 注册？
   └─ 是 → Plugin

2. 是否主要向 Agent 提供一个外部工具，并适合使用标准 MCP 协议？
   └─ 是 → MCP

3. 是否主要进行协议、消息、附件、身份、事件或错误模型转换？
   └─ 是 → Adapter

4. 是否是用户可请求、Agent 可选择、有明确交付物的任务或工作流？
   └─ 是 → Skill

5. 以上都不是？
   └─ 暂停创建 Extension，先补充需求和所有权边界。
```

“需要调用 AI”不是类型判断依据。关键是能力由谁触发、运行在哪一层、输出什么、是否需要修改 Runtime 生命周期。

## 2. 对比表

| 维度 | Skill | Plugin | Adapter | MCP |
| --- | --- | --- | --- | --- |
| 主要目的 | 完成用户任务 | 增强 Runtime | 转换协议/模型 | 暴露外部工具 |
| 触发者 | Agent/用户意图 | Runtime 生命周期或注册表 | Plugin、Channel、Core 调用方 | Agent Tool Router |
| Runtime 耦合 | 低到中 | 高 | 低 | 低到中 |
| 典型输入 | 任务参数、文件 | Runtime API/Event | Provider payload/model | MCP tool arguments |
| 典型输出 | 文本、结构化结果、artifact | 注册能力或 Runtime 行为 | 标准消息/错误/事件 | Tool result/resource |
| 是否独立进程 | 通常否 | 通常同进程 | 否 | 可以是 stdio/HTTP 服务 |
| 是否处理 Channel 生命周期 | 否 | 可以 | 否，只转换 | 否 |
| 凭据 | 引用，不保存 | 引用，不保存 | 不拥有 | Server/Runtime 注入 |
| 风险等级 | 中 | 高 | 低 | 中，取决于工具权限 |
| 示例 | PDF、DOCX、XLSX | 企业微信、Telegram、Provider | Channel 消息转换 | 搜索、数据库、API |

## 3. 什么时候创建 Skill

创建 Skill，当能力满足大部分条件：

- 用户可以直接提出该任务；
- Agent 需要根据意图或文件类型选择它；
- 有可描述的步骤、约束、输入、输出和验收标准；
- 输出是文本、结构化结果或文件制品；
- 能通过现有 Runtime 工具、脚本或 MCP 完成；
- 不要求应用启动时注册新 Runtime 能力。

适合示例：

- 编辑 PDF；
- 创建 Word、Excel、PPT；
- OCR 文档并输出 searchable PDF；
- 调用图片生成工具并验收图片 artifact；
- 编排搜索 MCP 后生成调研报告。

不要创建 Skill，当需求只是新增一个底层 API 客户端、消息格式转换或 Runtime Hook。

## 4. 什么时候创建 Plugin

创建 Plugin，当能力至少满足一个条件：

- 注册新的 Channel、模型 Provider、Tool Provider；
- 需要 Middleware 介入 AgentScope acting/reasoning；
- 需要应用启动/关闭 Hook；
- 新增全局命令、HTTP API 或 Console 前端页面；
- 必须由 Runtime 主动加载并维护生命周期；
- 要改变所有 Agent 或所有请求的系统级行为。

适合示例：

- 企业微信 Channel；
- Telegram Channel；
- 企业统一认证或审计 Middleware；
- 第三方模型 Provider；
- Runtime 级 Tracing/Observability。

不要创建 Plugin，当普通 Skill、MCP 或纯 Adapter 已能解决问题。Plugin 与 Runtime 同信任边界，错误可能影响整个实例。

## 5. 什么时候创建 Adapter

创建 Adapter，当需求主要是确定性的转换：

- Channel payload 转换为平台消息；
- 标准响应转换为 Channel 支持的文本、卡片或文件；
- 身份、conversation id、reply context 映射；
- 文件、图片、音频等附件描述转换；
- Runtime/Provider 错误映射为平台错误；
- 旧配置或旧 schema 转换为新 schema。

适合示例：

- `Telegram Update ↔ NormalizedMessage`；
- `WeCom callback ↔ NormalizedMessage`；
- `ResponseEvent → WeCom card/text`；
- 旧 MCP Driver 配置 → 新 `mcp.yaml`。

Adapter 不应调用模型、选择 Skill、保存凭据或决定业务流程。若需要建立连接、注册 Channel 或运行后台任务，应由 Plugin 拥有生命周期并调用 Adapter。

## 6. 什么时候创建 MCP

创建 MCP，当能力满足大部分条件：

- 核心价值是访问外部工具、数据或 API；
- 工具可以用稳定的 input/output schema 表达；
- 希望被多个 Agent、Skill 或应用复用；
- 适合独立进程或远程服务运行；
- 需要与 QwenPaw Runtime 解耦部署和升级；
- 已存在可靠 MCP Server 时优先复用，而不是重新封装 SDK。

适合示例：

- 搜索；
- 数据库只读查询；
- CRM/ERP/工单 API；
- 企业知识库；
- 文件转换或媒体处理服务。

不要创建 MCP，当能力需要介入 Runtime 生命周期，或只是一个 Skill 内部的纯函数。写数据库、发送消息、删除资源等高风险 MCP Tool 必须增加审批、权限和审计。

## 7. 常见组合决策

### 新增企业微信

```text
Plugin：注册 Channel、维护连接、回调、重连和健康状态
Adapter：企业微信消息/附件 ↔ 平台标准消息
Skill：不负责 Channel 接入
MCP：仅在需要把企业微信管理 API 暴露成 Agent 工具时使用
```

### 新增 Telegram

```text
Plugin：注册 Telegram Channel 和 polling/webhook 生命周期
Adapter：Telegram Update/Message ↔ 平台标准消息
Skill：只处理用户任务
```

### 新增数据库查询

```text
MCP：连接数据库并提供受控 query tools
Skill：可编排查询、分析和报告生成
Adapter：通常不需要，除非存在内部 schema 转换层
Plugin：通常不需要
```

### 新增图片生成

```text
MCP：已有远程生成服务并需要标准 Tool 协议时
Plugin：新增全局模型 Provider 或 Runtime Tool Provider 时
Skill：定义提示词、参数、重试、artifact 和质量验收工作流
Adapter：把 artifact 转成 Channel 支持的图片消息
```

### 新增 OCR

```text
Skill：用户可请求的 OCR 工作流与结果验收
MCP：OCR 是独立服务或被多个系统复用时
Adapter：统一不同 OCR Provider 的结构化结果时
Plugin：通常不需要
```

## 8. 边界冲突处理

当一个需求同时命中多类扩展时，按责任拆分，而不是选择一个“大而全”类型：

1. Runtime 注册和生命周期归 Plugin；
2. 确定性协议转换归 Adapter；
3. 外部工具执行归 MCP；
4. 用户任务编排和交付归 Skill。

禁止以下设计：

- Skill 内直接实现 Telegram/企业微信长连接；
- Adapter 内调用 LLM 决定业务动作；
- Plugin 内复制 PDF、DOCX 等文件处理逻辑；
- MCP Server 保存 Channel session 或替代 Channel Plugin；
- 为每个 Skill 修改 Agent、Streaming 或 Runtime；
- 在多个 Extension 中复制同一 Provider 凭据和 SDK 封装。

## 9. 创建前检查清单

- [ ] 已写明用户/系统触发方式。
- [ ] 已写明输入、输出、artifact 和错误。
- [ ] 已确认现有 Extension 不能直接复用。
- [ ] 已按快速决策树选定主类型。
- [ ] 跨类型责任已拆成独立目录和版本。
- [ ] 已确定凭据、网络、文件和数据库权限。
- [ ] 已确定本地测试与 Cloud staging 验收方法。
- [ ] 已确定 QwenPaw/schema 兼容范围。
- [ ] 已准备 README、CHANGELOG、tests 和回滚版本。
- [ ] 方案不要求修改 PDF、Agent、Streaming 或 Runtime 核心。

只有全部确认后才创建 Extension 目录。无法完成分类时，先提交架构决策记录，不进入实现。
