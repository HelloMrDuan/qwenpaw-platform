# Extension Contract 基线

## 1. 范围

本基线把 Phase 2 的消息、Streaming、Tool/Skill、Channel 和 Artifact 设计转换为可导入、可序列化、可离线验证的 Python 接口骨架。

它不提供：

- QwenPaw/AgentScope Runtime 实现或替代品；
- 事件总线、存储、网络和 Channel 连接；
- Skill Executor、Tool Router 或 Plugin Loader；
- Telegram、企业微信、微信或 Console 的真实 Adapter；
- PDF Editor 包装或行为修改。

## 2. 目录

```text
core/contracts/
├── __init__.py
├── artifact.py
├── channel.py
├── message.py
├── skill.py
└── streaming.py

tests/contracts/
├── __init__.py
├── test_message_contract.py
├── test_skill_channel_contracts.py
└── test_streaming_contract.py
```

## 3. 契约映射

| 模块 | 核心对象 | 对应设计 |
| --- | --- | --- |
| `message.py` | `MessageEvent`、`ChannelRef`、`UserRef`、`MessageContent` | `MESSAGE_MODEL_DESIGN.md` |
| `streaming.py` | `StreamEvent`、`StreamEventType`、`validate_stream_sequence` | `STREAMING_ARCHITECTURE.md` |
| `artifact.py` | `Artifact`、`ArtifactKind` | Message/Skill/File Event 的受控文件引用 |
| `skill.py` | `SkillMetadata`、`SkillRequest`、`SkillResult` | Skill Extension 输入输出边界 |
| `channel.py` | `ChannelAdapter`、`DeliveryReceipt` | Channel parse/send/render 最小接口 |

Python 对象的字段名为 `version`，序列化时使用设计文档中的 `schema_version`。`from_dict()` 同时接受这两个键作为迁移输入；两个键同时出现时必须一致。

## 4. 设计选择

- 使用 Python 3.11 标准库 `dataclass`、`Enum` 和 `Protocol`，不增加运行依赖。
- 数据对象为 frozen/slots dataclass，负责基础 schema 和跨字段校验，不执行 I/O。
- `ChannelAdapter` 是结构化 Protocol；任何真实实现都在未来的 Adapter/Plugin 目录中完成。
- `validate_stream_sequence()` 是纯函数，只验证一个 Stream 的顺序与生命周期，不缓存或发布事件。
- 文件只能使用 `artifact://` 引用；本契约不接受本地绝对路径作为 Artifact URI。
- `agent.cancelled` 作为设计文档已有的补充终态一并保留；用户要求的十个事件全部包含。

## 5. 本地测试

使用标准库运行：

```powershell
py -3.11 -m unittest discover -s tests/contracts -p "test_*.py" -v
```

测试完全离线，覆盖：

- Message、Artifact、Skill 和 Stream schema 的 JSON 往返；
- 版本、类型、时间、Artifact URI、Tool progress 等字段校验；
- Agent 首事件、事件 ID 唯一、严格递增序号、进度不倒退、Tool start/terminal 和 Agent 终态顺序；
- 使用 Fake Adapter 做 `ChannelAdapter` 结构检查，不连接真实 Channel。

## 6. 后续边界

后续实现应先增加 JSON Schema/fixture 兼容测试，再建立 Console 参考 Adapter。真实 Channel、Runtime Boundary Adapter 和 PDF Editor Tool Event Adapter 仍属于后续独立迁移，不在本基线内。
