# Extension Runtime Integration

状态：Phase 7.0 PDF Editor Extension Runtime Bridge。本文描述仓库 Extension 层的第一个真实 Skill 执行链路，不代表接入或替代 AgentScope/QwenPaw Runtime。

## 1. 当前执行链路

```text
SkillRequest
    │ skill_id=pdf-editor
    ▼
Extension Registry
    │ validated skills/pdf-editor/manifest.yaml
    ▼
ExtensionExecutorBridge
    │ allowlist + path + callable validation
    ▼
skills/pdf-editor/executor/main.py:execute
    │ existing Contract adapter
    ├── calls existing PDF Engine
    ├── returns StreamEvent[]
    └── returns Artifact[]
    ▼
SkillInvoker result validation
    │
    ├── StreamEvent → Extension StreamingBridge (optional)
    └── Artifact Result → caller-provided Artifact publisher
```

本阶段首次从统一 Extension Registry 发现 Skill Manifest，并通过统一 Runtime Bridge 调用已有 Skill executor。PDF 编辑算法、五层验收和底层子进程调用仍完全属于已有 PDF Editor executor/engine。

## 2. 组件职责

### ExtensionExecutorBridge

位置：`core/extensions/runtime/executor_bridge.py`。

负责：

- 从已发现的 Extension Registry 查询 Skill；
- 确认 Extension 类型是 `skill`、运行时是 `python`；
- 校验 Manifest executor 声明；
- 将 executor 相对路径约束在对应 Skill 目录；
- 加载声明的 callable；
- 传入既有 `SkillRequest`、Artifact resolver/publisher；
- 确认返回值是 `SkillResult`。

Phase 7.0 使用严格白名单，只允许：

```text
skill:      pdf-editor
executor:   skills/pdf-editor/executor/main.py
callable:   execute
runtime:    python
```

其他 Skill、Plugin、Adapter、路径或 callable 均被拒绝。该限制防止“通用动态代码加载器”在边界尚未生产化时扩大执行面。

### SkillInvoker

位置：`core/extensions/runtime/skill_invoker.py`。

Invoker 在事件发布前验证：

- `SkillResult.request_id` 与请求一致；
- 事件序号从1连续递增，`event_id` 唯一；
- 所有事件共享相同 stream/trace/session/conversation/task；
- 事件类型已在 Skill Manifest 声明；
- 事件 source 与 `pdf-editor` 身份一致；
- 成功链路从 `tool.start` 开始，以 `tool.result` 结束；
- `file.created` 与返回 Artifact ID 一致；
- 必需 Artifact 类型和 MIME 满足 Manifest 声明；
- 失败链路以 `tool.error` 结束。

验证成功后，Invoker 才会按顺序将事件交给可选的 Extension Streaming Publisher。

### Runtime Models

位置：`core/extensions/runtime/models.py`。

- `SkillExecutorDescriptor`：记录 Registry/Manifest 解析后的执行器身份；
- `SkillRuntimeResult`：组合执行器身份、`SkillResult` 和已发布事件数量；
- `ArtifactResolver`：把 Artifact 引用解析为本地输入路径；
- `ArtifactPublisher`：把 executor 临时输出发布为持久 Artifact；
- `StreamEventPublisher`：与现有 Extension Streaming Bridge 对接的最小接口。

## 3. PDF Editor边界

本阶段没有：

- 修改或复制 `skills/pdf-editor/scripts/pdf_editor.py`；
- 在 Runtime Bridge 中实现任何 PDF 文本、图片、字体或页面操作；
- 修改 `skills/pdf-editor/executor/main.py`；
- 绕过 PDF Editor 原有 Contract、PASS 验收或 Artifact publisher；
- 修改 PDF Editor Manifest。

Runtime Bridge 只调用已经存在并由 Manifest 声明的 executor。executor 继续负责调用原 PDF Engine。

## 4. StreamEvent语义

现有 PDF executor 在一次调用结束时返回完整 `SkillResult.events`。Invoker 校验后同步发布：

```text
tool.start
tool.progress *
file.created
tool.result
```

失败时：

```text
tool.start
tool.progress *
tool.error
```

Phase 7.0 的事件发布是“执行完成后的有序转发”，不是 Engine 子进程执行期间的实时跨进程流。真正的实时流式桥接需要未来定义进程事件传输、取消、背压和中断协议，不能修改 PDF Engine 临时实现。

## 5. Artifact语义

Runtime Bridge 不持久化文件。调用方必须提供：

1. `resolve_artifact(artifact)`：把输入 Artifact 安全解析为存在的本地文件；
2. `publish_artifact(path)`：在 executor 临时目录销毁前复制/上传输出，并返回正式 Artifact。

Invoker 只校验返回 Artifact 与 Manifest 输出契约及 `file.created` 事件一致。未来 Storage Provider 可实现本地对象存储、云对象存储或 Runtime 官方 Artifact API。

## 6. 与 QwenPaw Runtime 的边界

| Extension Runtime Bridge | AgentScope/QwenPaw Runtime |
| --- | --- |
| 仓库内 Registry 发现 | Agent/Planner 选择 Skill |
| 白名单 executor 加载 | Runtime 隔离、权限和进程管理 |
| SkillRequest/SkillResult 校验 | 用户、会话、任务调度 |
| Extension StreamEvent 转发 | Runtime 原生 Streaming 与 Channel 输出 |
| 调用方注入 Artifact resolver/publisher | 生产 Artifact Storage、签名URL和权限 |
| 单进程离线测试 | 超时、取消、重试、配额、审计和监控 |

当前 Bridge 不注册到云端 Runtime，不修改 Agent/Planner/Tool Router，也不接入 Gateway 或真实 Channel。

## 7. 后续生产化门槛

扩展到其他 Skill 或接入真实 Runtime 前至少需要：

- 基于部署制品而非开发源码的 executor 身份校验；
- Package签名、版本与 Lifecycle状态校验；
- 沙箱、资源限制、超时、取消和并发隔离；
- executor allowlist审批与依赖隔离；
- 实时事件传输、背压和失败补偿；
- Artifact访问控制、大小限制和恶意文件扫描；
- Runtime Provider及staging验收；
- 调用审计、指标和故障恢复。

完成这些边界前，不应把当前本地 Bridge 宣称为 QwenPaw Runtime 的替代实现。
