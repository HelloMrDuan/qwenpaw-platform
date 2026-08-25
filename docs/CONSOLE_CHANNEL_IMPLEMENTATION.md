# Console Channel Adapter 实施说明

## 1. 定位

Console Channel Adapter 是当前仓库第一个实现 `ChannelAdapter` Contract 的可执行 Extension Adapter。它验证统一消息、流事件、Renderer 和输出回执链路，但不包含 QwenPaw Runtime 或 Agent 执行。

```text
Console payload
    │ parse_message()
    ▼
MessageEvent(channel=console)
    │ future Runtime / test fixture creates StreamEvent
    ▼
send_stream_event(StreamEvent)
    │
    ▼
core.renderers.ConsoleRenderer
    │
    ▼
RenderedOutput
    │
    ▼
ConsoleOutputWriter
    │
    ▼
TextIO / stdout + DeliveryReceipt
```

## 2. 目录

```text
adapters/channels/console/
├── __init__.py
├── adapter.py
├── renderer.py
└── README.md
```

- `adapter.py`：实现 `parse_message()`、`send_message()` 和 `send_stream_event()`。
- `renderer.py`：把 `RenderedOutput` 写入可注入的文本流，不生成 StreamEvent。
- `core.renderers.ConsoleRenderer`：负责 `StreamEvent → RenderedOutput`，由 Phase 4.2 统一 Renderer 层维护。

## 3. 输入转换

当前 Console 输入只接受文本 payload：

```json
{
  "text": "生成报告",
  "user_id": "local-user",
  "platform_user_id": "usr_local",
  "display_name": "Local User",
  "message_id": "input-001",
  "trace_id": "trc_console_001",
  "session_id": "ses_console_001",
  "conversation_id": "conv_console_001",
  "timestamp": "2026-08-25T02:00:00Z",
  "metadata": {}
}
```

转换结果保证：

- `MessageEvent.version = message.v1`；
- `channel.type = console`；
- `channel.instance_id` 默认为 `console-local`；
- `user` 同时保留平台 ID 和 Console 外部 ID；
- `session_id`、`conversation_id`、`trace_id` 可由调用方提供；
- 未提供的本地关联 ID 使用 Console 默认值生成；
- `content.text` 为非空文本；
- `metadata.input_mode` 固定为 `console`。

文件、图片、音频和交互式终端读取暂不属于输入范围。未来应先转换为受控 Artifact，再扩展 MessageEvent 输入，不允许把本地绝对路径直接写入消息协议。

## 4. 输出转换

`send_stream_event()` 使用统一 `ConsoleRenderer`，然后由 `ConsoleOutputWriter` 展示：

| StreamEvent | RenderedOutput | Console 展示 |
| --- | --- | --- |
| `message.delta` | `text.delta` | 不加前缀，立即输出并 flush |
| `tool.start` / `tool.progress` / `tool.result` | `status` | `[status] ...` |
| `file.created` | `file` | `[file] name (artifact://...)` |
| `tool.error` / `agent.error` | `error` | `[error] safe message` |
| `agent.done` | `message` 或无新增输出 | 无 delta 时显示最终文本；已有 delta 时避免重复 |

Console 只展示 Artifact 受控 URI，不解析本地物理路径、不签发下载 token，也不读取文件内容。

## 5. DeliveryReceipt

- 成功写入文本流返回 `DeliveryStatus.SENT`；
- 无用户可见输出的 StreamEvent 返回 `None`；
- 文本流发生 `OSError` 时返回 `DeliveryStatus.FAILED` 和安全错误类型；
- `provider_message_id` 使用本地 Console delivery ID，只用于测试和关联，不代表外部 Provider 消息。

## 6. Runtime 边界

| Console Extension Adapter | QwenPaw Runtime / Agent |
| --- | --- |
| 解析显式传入的 Console payload | 负责真实用户输入循环或 Console 服务入口 |
| 生成标准 MessageEvent | 选择 Agent、Planner、Tool 和 Skill |
| 消费显式传入的 StreamEvent | 产生模型 token、Agent 生命周期与真实 Tool 事件 |
| 复用 Extension ConsoleRenderer | 决定 Runtime 内部调度和并发模型 |
| 写入 TextIO/stdout | 管理进程、网络、会话持久化和云端部署 |
| 返回本地 DeliveryReceipt | 维护生产级投递状态和可观测性 |

本实现不会注册到云端 Runtime，不推断 Runtime 内部入口，也不修改 Agent 配置、PDF Engine、任何 Skill 或现有 Channel。

## 7. 离线端到端测试

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests\channels\console -p "test_*.py" -v
```

测试链路：

```text
Console user payload
  → MessageEvent
  → fixture StreamEvent sequence
  → ConsoleRenderer
  → RenderedOutput
  → ConsoleOutputWriter(StringIO)
  → DeliveryReceipt
```

测试不启动 QwenPaw、不调用模型、不连接网络，也不执行或修改 PDF Editor。
