# 统一 Streaming 架构

## 1. 文档定位

本文定义 Agent 执行到 Channel 输出之间的目标事件协议。Streaming 是按序事件流，不等同于某个 Channel 原生支持 token stream。当前仓库没有实现该总线或 Renderer；本设计也不修改 AgentScope Runtime、现有 Channel 或 PDF Editor。

## 2. StreamEvent 信封

```json
{
  "schema_version": "stream.v1",
  "event_id": "evt_01K3C7E9K8",
  "event": "message.delta",
  "stream_id": "str_01K3C7E9K8",
  "sequence": 12,
  "timestamp": "2026-08-24T08:30:01Z",
  "trace_id": "trc_01K3C7E9K8",
  "session_id": "ses_01K3C7E9K8",
  "conversation_id": "conv_01K3C7E9K8",
  "task_id": "task_01K3C7E9K8",
  "source": {
    "type": "agent",
    "name": "default"
  },
  "payload": {}
}
```

规则：

- `sequence` 在一个 `stream_id` 内从 1 严格递增，是唯一排序依据。
- `event_id` 全局唯一，重放保持不变，消费者据此幂等处理。
- 一个 Stream 只允许一个终态：`agent.done`、`agent.error` 或 `agent.cancelled`。
- `trace_id` 连接入站消息、Agent Task、Tool Call、Artifact 与 Channel 投递。
- `source` 只能表达组件身份，不携带内部堆栈、凭据或私有推理。

## 3. 核心事件

| 事件 | 生产者 | 用户可见性 | Payload 最低字段 | 说明 |
| --- | --- | --- | --- | --- |
| `agent.start` | Agent Adapter | 可选 | `agent_id`, `accepted_at` | Agent Task 已接受，不表示已有答案 |
| `agent.thinking` | Agent Adapter | 默认不可见 | `status`, `safe_summary?` | 只允许安全状态摘要；禁止传输原始思维链 |
| `message.delta` | Agent Adapter | 是 | `delta`, `format` | 追加用户可见文本；初始 `format=text` |
| `tool.start` | Tool Router | 可选 | `tool_call_id`, `tool`, `tool_type` | Skill/MCP/Plugin/builtin 执行开始 |
| `tool.progress` | Tool Adapter | 可选 | `tool_call_id`, `progress`, `message?` | 可采样的进度事件 |
| `tool.result` | Tool Adapter | 通常摘要 | `tool_call_id`, `status`, `summary?` | Tool 成功终态，不内嵌大文件 |
| `file.created` | Artifact Store/Tool Adapter | 是 | `artifact` | 受控制品可供投递 |
| `agent.done` | Agent Adapter | 是 | `final`, `artifacts`, `usage?` | 成功终态和权威最终响应 |

异常终态：

| 事件 | 用途 |
| --- | --- |
| `agent.error` | Agent、Tool 或系统错误导致 Task 失败；包含标准 `code`、安全 `message`、`retryable` |
| `agent.cancelled` | 用户或系统取消；包含取消来源和已完成的安全摘要 |

`agent.thinking` 不是“暴露模型推理”的接口。Renderer 默认丢弃该事件；即使 Console 开启开发视图，也只能显示如“正在分析附件”的短状态，不得显示隐藏提示词、原始思维链或敏感 Tool 参数。

## 4. 典型生命周期

```text
agent.start
  ├─ agent.thinking*
  ├─ message.delta*
  ├─ tool.start
  │    ├─ tool.progress*
  │    ├─ file.created*
  │    └─ tool.result | tool.error
  ├─ message.delta*
  └─ agent.done | agent.error | agent.cancelled
```

`tool.error` 是 Tool Call 的终态，但不一定终止 Agent；Agent 可以选择降级、重试或生成解释。整个 Stream 仍必须以一个 `agent.*` 终态结束。

`agent.done.payload.final` 是最终用户文本的权威版本。收集全部 `message.delta` 应能得到相同文本；若 Runtime 只能给出最终文本，兼容 Adapter 可以产生单个 `message.delta` 后再产生 `agent.done`。

## 5. 事件示例

```json
{
  "schema_version": "stream.v1",
  "event_id": "evt_002",
  "event": "message.delta",
  "stream_id": "str_001",
  "sequence": 2,
  "timestamp": "2026-08-24T08:30:01Z",
  "trace_id": "trc_001",
  "session_id": "ses_001",
  "conversation_id": "conv_001",
  "task_id": "task_001",
  "source": {"type": "agent", "name": "default"},
  "payload": {"delta": "已完成前两页处理。", "format": "text"}
}
```

## 6. Channel Renderer 策略

核心事件不承诺每个 Channel 都实时展示每个 delta。Renderer 根据 Channel 能力选择输出策略：

| Channel | 目标策略 | 处理规则 |
| --- | --- | --- |
| Console | 实时输出 | 通过 CLI flush、SSE 或 WebSocket 消费事件；即时显示 `message.delta`、安全进度和 Artifact；终态关闭流 |
| Telegram | 消息更新 | 先发送占位消息，按节流窗口合并 delta 并 edit；遇到频率限制或编辑失败时退化为分段/最终新消息；终态执行最终 edit |
| 企业微信 | 分段回复 | 不假设原生 token streaming；按句子、长度和频率安全分段，保持序号与去重；无法主动更新时缓冲为最终回复 |
| 微信机器人/公众号 | 缓冲或受控分段 | 被动回复期限内优先 ACK/短回复；根据账号权限使用合规后续消息，否则只发送最终结果；不假设支持消息编辑 |

Renderer 能力应通过配置或运行时探测声明：

```json
{
  "supports_delta": false,
  "supports_edit": true,
  "supports_segment": true,
  "supports_artifact": true,
  "supports_progress": false,
  "max_text_length": 4096,
  "min_update_interval_ms": 1200
}
```

Agent 和 Skill 不读取这些 Channel 能力；只有 Stream Coordinator 与 Renderer 决定合并、节流和降级。

## 7. 顺序、重放与断线恢复

- 消费者记录每个 `stream_id` 的最后确认 `sequence`，重连时从下一序号恢复。
- 重复 `event_id` 直接忽略；相同 sequence 但不同 payload 是协议错误。
- 暂时缺失序号时短暂缓冲；超过窗口后转入安全失败或最终结果拉取，不能乱序展示。
- `agent.done` 必须包含完整最终文本与 Artifact 列表，使只拿到终态的 Channel 仍能正确交付。
- Channel 投递 ID 和已确认 sequence 保存在投递状态中，防止进程重启后重复发消息。

## 8. 背压、节流和资源限制

- Stream Coordinator 使用有界队列；队列满时优先合并连续 `message.delta`。
- `tool.progress` 可限频或采样；`tool.result`、`file.created` 和所有终态不可丢弃。
- 每个 Stream 设置最大事件数、缓冲字节、空闲时间和总截止时间。
- 慢 Channel 不阻塞 Agent 执行线程；可落入短期事件存储后异步投递。
- 超过 Provider 限流时采用带抖动退避，并遵守 Provider 返回的重试时间。

## 9. 取消与错误

- 用户取消产生标准取消请求，沿 Task → Tool Call 传播；成功处理后发出 `agent.cancelled`。
- 无法取消的外部工具可以继续隔离执行，但其晚到事件不得写入已终止 Stream。
- Tool 错误由 `TOOL_EVENT_PROTOCOL.md` 标准化，Agent 决定恢复还是终止。
- Channel 断开不自动取消持久 Task，除非该 Task 策略明确声明“连接即生命周期”。
- Channel 投递失败与 Agent 执行失败分开记录，避免把“答案已生成但发送失败”误判为 Agent 错误。

## 10. 安全与可观测性

- Channel 默认只消费 `message.delta`、安全的 Tool 摘要、`file.created` 和 Agent 终态。
- Tool 参数、完整结果、堆栈、凭据、下载令牌和私有路径不得进入可见事件。
- 指标记录事件延迟、队列深度、合并次数、重试、终态和 Channel 投递结果，不记录私有消息正文。
- 日志关联键为 `trace_id`、`stream_id`、`task_id`、`tool_call_id`、`event_id` 和 `sequence`。

## 11. 渐进落地顺序

1. 固化 schema 和纯内存 Collector，不连接真实 Channel。
2. 用 Console 最终文本构造 `agent.start → message.delta → agent.done`，验证收集结果与现状一致。
3. 增加 Tool Event 兼容 Adapter，不修改现有 Skill。
4. 建立 Console Renderer 和协议测试。
5. 最后按 Telegram、企业微信、微信的真实能力逐个接入，默认关闭并通过 staging 验收。

本阶段只完成设计文档，不执行上述实现步骤。
