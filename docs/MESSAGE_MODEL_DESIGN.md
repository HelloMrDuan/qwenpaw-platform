# 统一消息模型设计

## 1. 文档定位

本文定义 Phase 2 的目标输入契约 `MessageEvent`。它用于隔离 Console、Telegram、企业微信（WeCom）和微信（WeChat）的 Provider 差异，不代表当前仓库已经实现消息归一化代码，也不改变 QwenPaw/AgentScope Runtime。

设计原则：

1. Channel 只负责鉴权、收发、去重和协议转换，Agent 与 Skill 不读取 Provider 原始结构。
2. 文本、文件、图片、语音和事件消息使用同一个版本化信封。
3. 二进制内容进入受控存储后只传递 Artifact 引用，不在事件或日志中内嵌大对象。
4. 平台 ID 与 Provider ID 分离；所有时间使用 RFC 3339 UTC。
5. 未知字段可安全忽略，破坏性变更通过新的 `schema_version` 发布。

## 2. `MessageEvent` 信封

目标结构：

```json
{
  "schema_version": "message.v1",
  "id": "msg_01K3C7E9K8",
  "trace_id": "trc_01K3C7E9K8",
  "channel": {
    "type": "telegram",
    "instance_id": "telegram-main",
    "message_id": "provider-message-id",
    "thread_id": null,
    "tenant_id": null
  },
  "user": {
    "id": "usr_01K3C7E9K8",
    "external_id": "provider-user-id",
    "display_name": "optional display name",
    "tenant_id": null
  },
  "session_id": "ses_01K3C7E9K8",
  "conversation_id": "conv_01K3C7E9K8",
  "timestamp": "2026-08-24T08:30:00Z",
  "type": "text",
  "content": {
    "text": "请总结这个文件",
    "event": null
  },
  "attachments": [],
  "reply_to": null,
  "metadata": {}
}
```

### 2.1 字段约束

| 字段 | 必填 | 约束 |
| --- | --- | --- |
| `schema_version` | 是 | 初始值固定为 `message.v1` |
| `id` | 是 | 平台生成的全局唯一消息 ID；重投时保持不变 |
| `trace_id` | 是 | 贯穿 Channel、Agent、Tool 和 Streaming |
| `channel` | 是 | Channel 类型、实例、Provider 消息/线程和租户信息 |
| `user` | 是 | 平台用户 ID 与当前 Channel 身份；不以显示名作为身份键 |
| `session_id` | 是 | 当前 Channel 会话范围，规则见 `SESSION_MODEL.md` |
| `conversation_id` | 是 | 当前逻辑对话，可在明确授权后跨 Channel 恢复 |
| `timestamp` | 是 | Provider 时间或接收时间，统一为 RFC 3339 UTC |
| `type` | 是 | `text`、`file`、`image`、`audio`、`event` 或 `mixed` |
| `content` | 是 | 用户可见文本或结构化事件；允许空文本但不能与消息类型矛盾 |
| `attachments` | 是 | Artifact 描述数组；无附件时为空数组 |
| `reply_to` | 否 | 被回复消息的标准 ID 与可选 Provider ID |
| `metadata` | 是 | 有大小限制、经过脱敏的扩展字段；无数据时为空对象 |

`channel.type` 初始允许 `console`、`telegram`、`wecom.bot`、`wecom.kf`、`wechat.mp` 和 `wechat.bot`。将企业微信与微信分开命名，避免把不同身份、回调和回复约束混为一个 Channel。

## 3. 内容类型

| `type` | 表达方式 | 说明 |
| --- | --- | --- |
| `text` | `content.text` | 普通文本、命令或图片说明文字 |
| `file` | `attachments[].kind=file` | PDF、Office、压缩包等普通文件 |
| `image` | `attachments[].kind=image` | 单图或多图；缩略图不是新的用户消息 |
| `audio` | `attachments[].kind=audio` | 语音和音频统一为 `audio`，语音在附件元数据中标记 `voice=true` |
| `event` | `content.event` | 加群、关注、菜单点击、消息编辑、撤回等非内容消息 |
| `mixed` | 文本加一个或多个附件 | 例如 Telegram caption + document |

事件消息结构：

```json
{
  "type": "event",
  "content": {
    "text": null,
    "event": {
      "name": "channel.message.edited",
      "payload": {
        "target_message_id": "msg_01K3C7E9K8"
      }
    }
  }
}
```

事件名采用命名空间格式。未知事件可以保存并路由到审计，但默认不触发 Agent。

## 4. Attachment/Artifact 描述

```json
{
  "id": "art_01K3C7E9K8",
  "kind": "file",
  "name": "contract.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 483920,
  "uri": "artifact://incoming/art_01K3C7E9K8",
  "sha256": "optional-lowercase-hex",
  "duration_ms": null,
  "dimensions": null,
  "metadata": {}
}
```

约束：

- `uri` 必须是存储层返回的受控引用，不暴露本地绝对路径、临时下载 URL 或访问令牌。
- 文件名、MIME、大小和实际内容必须在进入 Agent 前校验；不信任 Provider 声明。
- 图片可增加 `{width, height}`，音频可增加 `duration_ms`，但这些扩展不改变基础协议。
- 同一 Provider 文件重投时可复用 Artifact，但必须重新执行访问控制检查。

## 5. Channel 转换规则

| Channel | 入站来源 | `MessageEvent` 映射 | 特殊约束 |
| --- | --- | --- | --- |
| Console | CLI/Console 文本和本地上传 | 当前账号/本机主体映射为 `user`；Console 会话映射为 `session_id`；上传文件进入 Artifact 存储 | Phase 2 首个参考 Adapter；不得把任意本地路径直接交给 Agent |
| Telegram | Bot Update、message、callback | bot 实例、chat、message、topic/thread 和 sender 分别映射到 `channel`、Session 与 `user`；text/caption 进入 `content.text`；document/photo/voice 下载后生成 Artifact | 使用 Update/message ID 去重；bot token、file URL 不进入模型、事件或日志；编辑与 service message 转为 `event` |
| WeCom | 企业微信机器人或微信客服回调/轮询 | `wecom.bot` 与 `wecom.kf` 分离；企业/客服实例进入 tenant/instance；外部联系人映射为 ChannelIdentity；media 下载后生成 Artifact | webhook 验签先于归一化；callback 与 polling 使用同一 Provider 消息 ID 去重；外部服务源码未在仓库内，不宣称已实现 |
| WeChat | 微信公众号或机器人回调/XML | `wechat.mp`/`wechat.bot` 实例、OpenID/用户标识、消息 ID 和事件名分别映射；图片、语音先落 Artifact | 被动回复时限与主动消息权限属于 Renderer capability，不写入 Agent 逻辑；XML 原文默认不保留 |

Provider 特有字段只能放在带命名空间的元数据中，例如 `metadata.telegram`。只有 Adapter 或 Renderer 可以依赖这些字段，Agent、Planner、Skill 和 MCP 不得依赖。

## 6. 身份、去重与排序

- `id` 由 `channel.type + instance_id + tenant_id + provider message_id` 的稳定映射生成或登记。
- Provider 重发相同消息时复用 `id`，不得重复创建 Agent Task。
- `timestamp` 用于展示和审计；同一 Session 的处理顺序由 Channel 序号或接收序号决定。
- 消息编辑、撤回不覆盖原始 `MessageEvent`，而是产生引用原消息的新 `event`。
- 群聊身份同时包含群/线程 Session 和发送者 ChannelIdentity；群聊与私聊绝不自动合并。

## 7. 校验、错误与安全

归一化发生在 Agent 调用之前。失败时生成内部标准错误并由 Channel Adapter 给出安全回复，不构造半有效消息。

最低校验包括：

- webhook 签名、时间窗口和重放保护；
- schema、消息大小、附件数量、MIME、扩展名和实际文件签名；
- tenant、Channel 实例、用户和会话访问策略；
- `metadata` 大小与字段白名单；
- URL、文件名、显示名和 Provider 原始内容的日志脱敏。

不得将凭据、签名密钥、完整 Provider 原始 payload、无限期下载 URL或私有本地路径写入 `MessageEvent`。为诊断保留原始请求时，应放入隔离审计存储，仅在 `metadata` 中记录脱敏引用。

## 8. 版本与兼容

- `message.v1` 内可以增加可选字段；消费者必须忽略未知可选字段。
- 删除字段、改变语义或枚举含义需要 `message.v2`。
- 现有 `CHANNEL_DESIGN.md` 中的 `NormalizedMessage` 是早期逻辑模型；实现迁移时通过兼容映射转换为本契约，不要求一次性修改所有调用方。
- schema 发布后必须包含正向、反向、未知字段、重复消息和非法附件 fixture。

## 9. 设计验收标准

1. 同一用户意图从四类 Channel 输入时，Agent 可见的核心字段保持一致。
2. Agent 与 Skill 不需要读取 Telegram/WeCom/WeChat 原始 payload。
3. 文本、文件、图片、语音和事件均可无损表示。
4. 重投不会创建第二个 Agent Task。
5. 任何消息或附件引用都不暴露凭据和不受控文件路径。
