# Stream Renderer 架构设计

## 1. 目标

Renderer 位于标准 `StreamEvent` 与真实 Channel 投递之间，将事件转换为传输无关的展示动作。它解决不同渠道对实时 delta、消息编辑、分段、文件和错误展示能力不同的问题，但不负责调用渠道 API。

```text
Skill / Agent Adapter
        │
        ▼
   StreamEvent
        │
        ▼
Streaming Bridge / Coordinator
        │
        ▼
  StreamRenderer
        │
        ▼
 RenderedOutput
        │
        ▼
future Channel Adapter
        │
        ▼
Console / Telegram / WeCom / WeChat
```

## 2. Renderer Contract

```python
class StreamRenderer(Protocol):
    channel_type: str

    def render(event: StreamEvent) -> Sequence[RenderedOutput]: ...
    def flush() -> Sequence[RenderedOutput]: ...
    def close() -> Sequence[RenderedOutput]: ...
```

- `render(event)`：消费一个已排序事件，可能立即生成零个、一个或多个展示动作。
- `flush()`：在不关闭 Renderer 的情况下输出当前缓冲内容。
- `close()`：输出剩余缓冲并关闭；关闭后拒绝新事件。

一次事件返回零个输出是正常行为，例如 Telegram 未达到更新阈值或 WeChat 仍在缓冲。

## 3. Channel Output 模型

`RenderedOutput` 是 Renderer 和未来 Channel Adapter 之间的中间协议，不是实际发送结果，也不是 `DeliveryReceipt`。

主要字段：

| 字段 | 用途 |
| --- | --- |
| `id` | Renderer 输出动作 ID |
| `schema_version` | 当前为 `render.output.v1` |
| `type` | `text.delta`、`message`、`message.update`、`status`、`file`、`error` |
| `channel` | 目标策略类型，不是账号或租户凭据 |
| `session_id` / `stream_id` | 与输入事件关联 |
| `sequence` | 本动作涉及的最大源事件序号 |
| `source_event_ids` | 形成该动作的原始事件 ID，用于追踪和幂等 |
| `text` | 用户可见文本或安全状态摘要 |
| `artifact` | `file` 输出对应的受控 Artifact 描述 |
| `final` | 是否为该策略确认的最终展示 |
| `metadata` | 分段、节流或文件交付提示，不包含 Provider 凭据 |

## 4. 渠道策略

### ConsoleRenderer

- `message.delta` 立即转换为 `text.delta`；
- 安全的 Agent/Tool 状态立即转换为 `status`；
- `file.created` 转换为 Artifact 引用；
- `tool.error` / `agent.error` 立即转换为 `error`；
- 已展示 delta 时不重复输出 `agent.done.final`。

### TelegramRenderer

- 聚合连续 `message.delta`；
- 达到字符阈值后生成首次 `message`；
- 后续达到阈值或调用 `flush()` 时生成完整内容的 `message.update`；
- `agent.done` 使用权威最终文本完成最后一次更新；
- 当前阈值模拟节流窗口，不实现 Provider 计时器或限流重试。

### WeComRenderer

- 按配置字符上限把 delta 转换为多个 `message` 分段；
- 不足一段的余量保留到 `flush()` 或 Agent 终态；
- 每个分段保留源事件 ID 和最大 sequence；
- `file.created` 生成 `file_message` 建议动作；
- 不假设企业微信支持原生 token streaming 或消息编辑。

### WeChatRenderer

- 默认缓冲所有文本 delta；
- 只在 `flush()`、`agent.done` 或错误边界生成完整回复；
- `file.created` 生成 `download_link` 建议动作；
- 不假设微信账号具备主动消息、消息编辑或任意文件上传权限。

## 5. 文件事件处理

`file.created.payload.artifact` 必须是完整 Artifact 描述。Renderer 只保留 `artifact://` 受控引用并声明未来的交付策略：

| Renderer | `artifact_delivery` | 后续 Channel Adapter 行为 |
| --- | --- | --- |
| Console | `artifact_reference` | 显示受控文件引用或由本地 Artifact 服务解析 |
| Telegram | `attachment_or_link` | Provider 支持时上传附件，否则使用短期下载链接 |
| WeCom | `file_message` | 上传临时素材并发送文件消息，失败时降级为链接 |
| WeChat | `download_link` | 按账号能力发送合规下载链接或延迟交付提示 |

Renderer 不生成签名 URL、不读取本地路径、不上传文件。未来 Artifact Delivery Adapter 应：

1. 根据 Artifact ID 验证调用方和 session 权限；
2. 选择 Provider 上传或短期签名下载链接；
3. 设置最短可用过期时间，禁止把 token 写入事件日志；
4. 返回独立 `DeliveryReceipt`；
5. 将文件发送失败与 Agent/Skill 执行失败分开记录。

## 6. 顺序、缓冲与终态

- Renderer 独立校验同一 `stream_id` 的 sequence 严格递增。
- 重复 `event_id` 拒绝处理，防止重复展示。
- trace、session、conversation 和 task 关联字段不可在流中变化。
- `flush()` 不关闭流，后续仍可 `render()`。
- `close()` 必须先输出剩余缓冲；重复关闭为无操作。
- 已关闭 Renderer 不接受新事件。
- Stream 生命周期和 Tool 前后关系仍由 Streaming Bridge/Runtime 负责，Renderer 只防御展示层乱序。

## 7. 错误与安全

- `tool.error` 和 `agent.error` 只显示标准安全 `message`/`code`，不显示堆栈、隐藏提示词或原始 Tool 参数。
- `agent.thinking` 默认只允许 `safe_summary` 或短状态，不允许原始思维链。
- 文件输出不得包含本地绝对路径、Provider token 或永久公开链接。
- Renderer 错误属于展示转换错误，不应改写 Agent 或 Skill 的执行结果。

## 8. 非目标

本阶段不实现真实 Channel、Provider SDK、网络发送、SSE/WebSocket、异步任务队列、持久化节流状态、限流退避或 Runtime 生命周期，也不修改 Agent、PDF Editor 或 QwenPaw Runtime。
