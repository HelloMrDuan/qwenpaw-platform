# Unified Streaming Design

## 1. Goal

Provide one ordered response-event contract between Agent execution and channel rendering without changing AgentScope core or requiring every channel to support native token streaming.

## 2. Principles

1. Streaming is an event protocol, not a transport assumption.
2. Final buffered output must be derivable from the same event sequence.
3. Tool activity and generated artifacts are first-class events.
4. Every event is ordered, traceable, cancellable, and safe to log after redaction.
5. Channel adapters select native streaming, message editing, batching, or final-only rendering.

## 3. Event envelope

Target envelope:

```json
{
  "schema_version": 1,
  "stream_id": "stream-id",
  "trace_id": "trace-id",
  "sequence": 1,
  "timestamp": "2026-08-24T00:00:00Z",
  "type": "response.delta",
  "payload": {
    "text": "partial text"
  }
}
```

Required properties:

- `stream_id` identifies one Agent response.
- `trace_id` correlates channel, Agent, planner, tool, and Skill activity.
- `sequence` is strictly increasing within a stream.
- `type` selects a versioned payload schema.
- `timestamp` is diagnostic; ordering relies on `sequence`.

## 4. Initial event types

| Event | Purpose |
| --- | --- |
| `response.start` | Opens a response stream and declares capabilities |
| `response.delta` | Adds user-visible text or structured content |
| `response.replace` | Replaces accumulated content when a renderer supports editing |
| `tool.start` | Announces a tool or Skill invocation |
| `tool.progress` | Emits bounded progress without exposing private arguments |
| `tool.result` | Emits a safe result summary |
| `artifact.ready` | Makes a validated artifact available for delivery |
| `response.warning` | Reports degraded but continuing behavior |
| `response.error` | Terminates with a normalized failure |
| `response.cancelled` | Terminates after cancellation |
| `response.complete` | Terminates successfully with final metadata |

Existing PDF Editor progress output is adapted at the Tool Router boundary; PDF Editor itself is not changed during the streaming migration.

## 5. Stream lifecycle

```text
created
  └─ response.start
       ├─ response.delta / response.replace
       ├─ tool.start → tool.progress* → tool.result
       ├─ artifact.ready
       └─ response.complete | response.error | response.cancelled
```

Rules:

- Exactly one terminal event is allowed.
- Events after a terminal event are rejected and recorded as protocol violations.
- Missing sequence numbers cause buffering or stream failure according to timeout policy.
- Duplicate sequence numbers are ignored only when payload checksums match.

## 6. Rendering modes

### Native stream

Used when the channel supports streaming responses. Deltas are forwarded with provider-specific throttling.

### Edit-based stream

Used when the provider supports editing a previously sent message. Deltas are accumulated and the message is updated at a bounded interval.

### Batched stream

Used when frequent edits are expensive or rate-limited. Deltas are emitted in larger chunks.

### Final-only

Used when the provider has no practical streaming mechanism. The adapter buffers safe user-visible content and sends once at completion.

All four modes consume the same event sequence.

## 7. Backpressure and limits

- Producers write to a bounded queue.
- Renderers acknowledge consumed sequence numbers.
- Slow channels trigger coalescing of compatible text deltas.
- Tool progress events may be sampled; terminal and artifact events may not be dropped.
- Maximum buffered bytes, event count, and idle duration are configuration values.
- Exceeding a hard limit produces a normalized terminal error or safe final-only fallback.

## 8. Cancellation and timeout

- User cancellation marks the stream cancelled and propagates a cancellation token to Agent and tool adapters.
- A tool that cannot cancel is detached from channel delivery and its late output is discarded or quarantined.
- Channel disconnect does not automatically cancel durable work unless the request policy says so.
- Deadlines are absolute and propagated across nested tool calls.

## 9. Security and privacy

- Tool arguments and results are redacted before events reach channels.
- Internal reasoning is not a response event.
- Artifact events expose controlled descriptors, not unrestricted local paths.
- Logs store event metadata and safe summaries, not credentials or private binary content.
- Error payloads use normalized codes and omit raw stack traces by default.

## 10. Incremental migration

1. Define event schemas and a pure in-memory collector.
2. Adapt existing Console final output into `start`, `delta`, and `complete` events.
3. Prove that collecting events reproduces the current final response.
4. Add Console live rendering.
5. Adapt tool progress at the Tool Router boundary.
6. Add channel-specific renderers one at a time.
7. Enable streaming per channel only after rate-limit and reconnect tests pass.

No streaming implementation is part of the architecture baseline commit.
