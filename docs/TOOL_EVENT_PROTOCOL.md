# Tool / Skill 事件协议

## 1. 目标与范围

本协议统一 Skill、MCP、Plugin 和 Runtime builtin tool 的执行事件，使 Agent 与 Streaming 层不依赖具体工具的日志格式。Tool 事件使用 `STREAMING_ARCHITECTURE.md` 的 `stream.v1` 信封。

它是目标协议，不修改 PDF Editor、Tool Router、AgentScope Runtime 或现有 MCP Driver。

## 2. Tool Call 状态机

```text
tool.start
  ├─ tool.progress*
  ├─ file.created*
  └─ tool.result | tool.error
```

规则：

1. 每个 `tool_call_id` 恰好一个 `tool.start` 和一个终态 `tool.result` 或 `tool.error`。
2. `tool.progress` 与 `file.created` 只能出现在开始与终态之间。
3. Tool 终态不等于 Agent 终态；Agent 可以继续调用工具或返回降级结果。
4. 重试创建新的 `tool_call_id`，通过 `retry_of` 关联原调用，避免混淆两次执行。
5. 嵌套调用使用 `parent_tool_call_id`，并保持同一 `trace_id` 与 `task_id`。

## 3. 公共字段

所有 Tool Event 的 `payload` 至少包含：

| 字段 | 说明 |
| --- | --- |
| `tool_call_id` | 一次执行的稳定 ID |
| `parent_tool_call_id` | 可选；编排或嵌套调用的父 ID |
| `tool_type` | `skill`、`mcp`、`plugin` 或 `builtin` |
| `tool` | 稳定工具 ID，例如 `pdf-editor`、`tavily-search` |
| `operation` | 可选的稳定操作名，例如 `replace_text` |
| `attempt` | 从 1 开始的尝试次数 |

公开事件只能带经过脱敏、截断的 `input_summary` 或 `result_summary`，不得携带完整提示词、凭据、用户文件内容和无界 Tool 输出。

## 4. `tool.start`

```json
{
  "schema_version": "stream.v1",
  "event_id": "evt_tool_001",
  "event": "tool.start",
  "stream_id": "str_001",
  "sequence": 4,
  "timestamp": "2026-08-24T08:30:02Z",
  "trace_id": "trc_001",
  "session_id": "ses_001",
  "conversation_id": "conv_001",
  "task_id": "task_001",
  "source": {"type": "tool-router", "name": "default"},
  "payload": {
    "tool_call_id": "call_001",
    "parent_tool_call_id": null,
    "tool_type": "skill",
    "tool": "pdf-editor",
    "operation": "replace_text",
    "attempt": 1,
    "input_summary": "处理 1 个 PDF 文件"
  }
}
```

开始事件表示调用已通过路由与基础校验，不表示 Tool 已成功完成。

## 5. `tool.progress`

```json
{
  "schema_version": "stream.v1",
  "event_id": "evt_tool_002",
  "event": "tool.progress",
  "stream_id": "str_001",
  "sequence": 5,
  "timestamp": "2026-08-24T08:30:03Z",
  "trace_id": "trc_001",
  "session_id": "ses_001",
  "conversation_id": "conv_001",
  "task_id": "task_001",
  "source": {"type": "skill", "name": "pdf-editor"},
  "payload": {
    "tool_call_id": "call_001",
    "parent_tool_call_id": null,
    "tool_type": "skill",
    "tool": "pdf-editor",
    "operation": "replace_text",
    "attempt": 1,
    "progress": {
      "percent": 50,
      "current": 2,
      "total": 4,
      "unit": "page"
    },
    "message": "正在替换第2页"
  }
}
```

进度约束：

- `percent` 可选；存在时为 0–100 且同一次调用不应倒退。
- 无法量化时可只给 `current/total/unit` 或安全 `message`。
- 高频 Tool 进度可被 Stream Coordinator 合并或采样。
- `message` 面向用户时必须脱敏；详细诊断只写隔离日志。

## 6. `file.created`

```json
{
  "event": "file.created",
  "payload": {
    "tool_call_id": "call_001",
    "tool_type": "skill",
    "tool": "pdf-editor",
    "artifact": {
      "id": "art_001",
      "name": "contract-edited.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 490112,
      "uri": "artifact://outputs/art_001",
      "sha256": "optional-lowercase-hex"
    }
  }
}
```

`file.created` 只在文件已经写入受控存储、通过最低完整性校验并具备访问策略后发出。Tool 返回的本地路径先由 Artifact Adapter 接管，不能直接发给 Channel。

## 7. `tool.result`

```json
{
  "event": "tool.result",
  "payload": {
    "tool_call_id": "call_001",
    "parent_tool_call_id": null,
    "tool_type": "skill",
    "tool": "pdf-editor",
    "operation": "replace_text",
    "attempt": 1,
    "status": "succeeded",
    "summary": "已完成 4 页文本替换并生成 1 个文件",
    "artifact_ids": ["art_001"],
    "metrics": {"duration_ms": 2180}
  }
}
```

大结果使用 Artifact 或受控 Result 引用。`summary` 是安全的人类可读摘要，不代替 Agent 根据结果生成最终答复。

## 8. `tool.error`

```json
{
  "event": "tool.error",
  "payload": {
    "tool_call_id": "call_001",
    "parent_tool_call_id": null,
    "tool_type": "skill",
    "tool": "pdf-editor",
    "operation": "replace_text",
    "attempt": 1,
    "error": {
      "code": "TOOL_INPUT_UNSUPPORTED",
      "message": "该 PDF 暂不支持当前编辑方式",
      "retryable": false,
      "category": "validation",
      "details_ref": "diag://tool-errors/err_001"
    }
  }
}
```

错误分类建议：`validation`、`permission`、`dependency`、`timeout`、`cancelled`、`provider`、`internal`。`details_ref` 只允许受权限控制的诊断引用；Channel 不展示堆栈和内部路径。

## 9. 不同扩展类型的映射

| 类型 | 事件映射 |
| --- | --- |
| Skill | Skill Loader/Executor Adapter 发出 start/result/error；可选把结构化进度映射为 progress，制品映射为 file.created |
| MCP | MCP Client 发出 start/result/error；Server 支持 progress notification 时映射为 progress，否则不伪造百分比 |
| Plugin | 只有被 Agent 当作 Tool 调用的 Plugin 能力使用本协议；生命周期 Hook 不产生 Tool Event |
| builtin | Runtime Boundary Adapter 将官方工具事件映射到协议；缺少细粒度事件时只发 start + result/error |

## 10. PDF Editor 兼容策略

PDF Editor 保持现有实现不变。未来兼容 Adapter 可以：

1. 在调用前产生 `tool.start`；
2. 若现有进度输出可用，将其 JSONL/结构化进度映射为 `tool.progress`；
3. 将经过验证的输出文件登记为 Artifact 后产生 `file.created`；
4. 将最终结构化结果映射为 `tool.result`，非零退出或标准错误映射为 `tool.error`。

Adapter 不能解析非稳定的人类日志来伪造可靠百分比；无法识别时只提供开始和终态。该方案把变化限制在未来的 Tool 边界，不修改 `skills/pdf-editor/`。

## 11. 安全、幂等与测试

- `tool_call_id + event_id` 用于去重；重复事件必须内容一致。
- Tool 参数先过 schema、权限、路径和资源额度校验，再产生 `tool.start`。
- Result/Artifact 在产生事件前执行访问控制、大小、类型和恶意内容检查。
- 取消后晚到的 progress/result 不得进入已终止 Stream，只能进入隔离审计。
- 契约测试至少覆盖成功、进度、无进度、文件产出、超时、取消、重试、嵌套调用、重复事件和脱敏。

## 12. 设计验收标准

1. Skill、MCP、Plugin Tool 和 builtin tool 可被同一 Stream Consumer 处理。
2. 有进度的 Tool 可报告进度，无进度的 Tool 不需要模拟进度。
3. Tool 文件结果只通过受控 Artifact 引用交付。
4. Tool 失败不必强制整个 Agent Task 失败。
5. PDF Editor 无需修改即可在未来通过边界 Adapter 接入。
