# Channel Design

## 1. Scope

This document defines the target contract for Console, Telegram, WeCom, WeChat, and future message channels. It does not enable a channel or change existing AgentScope channel behavior.

## 2. Design rule

A channel is a transport adapter. It translates provider payloads into normalized messages and translates response events into provider operations. It must not own model selection, planning, tool routing, or Skill logic.

```text
Provider payload
    ↓ decode / authenticate / deduplicate
Channel adapter
    ↓
NormalizedMessage
    ↓
AgentScope adapter
    ↓
ResponseEvent stream
    ↓ render / edit / buffer / upload
Channel adapter
    ↓
Provider API
```

## 3. Normalized inbound message

Target shape:

```json
{
  "schema_version": 1,
  "message_id": "channel-stable-id",
  "trace_id": "platform-trace-id",
  "channel": "telegram",
  "conversation": {
    "id": "normalized-conversation-id",
    "type": "direct"
  },
  "sender": {
    "id": "channel-user-id",
    "display_name": "optional"
  },
  "parts": [
    {"type": "text", "text": "hello"}
  ],
  "reply_to": null,
  "received_at": "2026-08-24T00:00:00Z",
  "capabilities": {
    "streaming": false,
    "message_edit": true,
    "attachments": true
  },
  "metadata": {}
}
```

`metadata` may retain redacted provider information needed for delivery or diagnostics. Agent and Skill code must not depend on provider-specific metadata.

## 4. Content parts

Initial content types:

- `text`
- `image`
- `file`
- `audio`
- `video`
- `location`
- `reference`

Binary content is represented by a controlled artifact reference with media type, size, checksum, and optional filename. Channel URLs and credentials must not leak into Agent prompts when an artifact reference is sufficient.

## 5. Channel adapter contract

A future channel adapter should provide logical operations equivalent to:

- start and stop lifecycle;
- receive and normalize inbound messages;
- acknowledge delivery when required;
- send or update text;
- upload and send artifacts;
- render response events;
- propagate cancellation when the provider supports it;
- expose health and readiness state.

The exact programming interface is deferred to Phase 2. The behavior contract is fixed before code is introduced.

## 6. Reliability requirements

### Idempotency

Inbound provider IDs are mapped to a stable deduplication key. Redelivery must not run the Agent twice unless an explicit replay operation requests it.

### Ordering

Messages within one conversation retain provider order. Stream events are applied only when their sequence number is newer than the last accepted sequence.

### Retries

Retry only errors classified as retryable. Outbound retries must reuse an idempotency key where the provider supports it.

### Rate limits

Adapters translate provider rate-limit responses into normalized retry hints and avoid blocking the Agent execution thread.

### Attachments

Validate media type, size, checksum, and workspace path before download or upload. Temporary files use controlled storage and cleanup rules.

## 7. Security requirements

- Resolve credentials from ignored local configuration or a secret provider.
- Never serialize credentials into normalized messages or stream events.
- Verify webhook signatures before normalization.
- Redact provider payloads before logging.
- Apply allowlists and conversation access policies before Agent execution.
- Keep user identity mapping scoped to the channel and tenant.

## 8. Channel capability strategy

| Channel | Current state | First migration behavior |
| --- | --- | --- |
| Console | Enabled | Reference normalization and renderer |
| Telegram | QwenPaw v2.1.0 built-in | Configure and accept built-in streaming, typing, proxy, and access control |
| WeCom | QwenPaw v2.1.0 built-in | Configure and accept built-in authorization, media, and group context |
| WeChat | QwenPaw v2.1.0 built-in | Configure and accept the built-in login/Bot Token model |
| WeChat Customer | Custom / to verify | Preserve Gateway/cursor/DB boundary while checking built-in coverage |

Channel capabilities are negotiated. The core emits one response-event model; the adapter may stream natively, edit a message periodically, or buffer until completion.

## 9. Migration order

1. Capture Console fixtures and behavior.
2. Implement and validate normalization with Console only.
3. Define response rendering against the streaming contract.
4. Validate Telegram through the built-in Channel; do not implement a replacement Adapter/BaseChannel.
5. Validate WeCom through the built-in Channel; retain recovered assets only as fallback/reference.
6. Validate built-in WeChat separately from the historical WeChat Customer chain.
7. Decide whether WeChat Customer needs a custom integration only after callback, cursor, database, deduplication, and API constraints are verified.
