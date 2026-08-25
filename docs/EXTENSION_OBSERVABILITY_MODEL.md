# Extension Observability Model

## 1. Purpose and boundary

Phase 7.8 introduces a passive, local observability foundation for Extension
development and offline Runtime integration. It records data supplied by an
Extension caller; it does not instrument, start, stop, retry, or otherwise
change an Extension.

```text
Extension
    |
    v
Lifecycle observation
    |
    v
Health observation
    |
    v
Event Trace correlation
```

The foundation is located in `core/extensions/observability/`. It does not
modify QwenPaw/AgentScope Runtime, the Agent loop, historical Gateways, Message
Model, or Streaming core.

## 2. Observation model

All records use schema version `qwenpaw-extension-observability.v1` and always
carry `extension_name`. The first version defines four immutable records:

| Record | Purpose | Main fields |
| --- | --- | --- |
| `ExtensionStateObservation` | Snapshot a supplied `LifecycleRecord` | version, state, revision, action, error, observed_at |
| `ExtensionHealthObservation` | Snapshot a supplied `HealthReport` | healthy, verification/probe flags, code, message, trace_id |
| `ExtensionCallMetrics` | Atomic invocation totals | calls, successes, failures, updated_at |
| `ExtensionTraceEvent` | Associate an event with an Extension and trace | trace_id, event_id, event_type, session_id, sequence, metadata |

Records validate UTC timestamps and expose JSON-compatible `to_dict()` output.
They contain no credential or provider secret fields.

## 3. Lifecycle and health history

`ExtensionHealthStore` accepts existing Lifecycle and Health models:

```python
store.record_state(lifecycle_record)
store.record_health(health_report, trace_id="trace-optional")
```

State and health are separate histories because a lifecycle transition does
not necessarily perform a Runtime probe, and a health probe does not always
cause a lifecycle transition. Queries are isolated by Extension:

- `state_history(name)` and `latest_state(name)`;
- `health_history(name)` and `latest_health(name)`;
- `extension_names()` for names observed in either history.

Each history is bounded independently per Extension. The default keeps the
latest 100 state records and 100 health records in process memory. Recording
does not mutate the supplied `LifecycleRecord` or `HealthReport`.

## 4. Invocation metrics

`ExtensionMetricsStore.record_call(name, success=...)` records one completed
invocation atomically. Each call increments exactly one terminal outcome, so
the following invariant always holds:

```text
calls = successes + failures
```

`get(name)` returns one immutable snapshot and `list()` returns stable,
name-sorted snapshots. Counts are isolated by Extension name. This first phase
does not collect duration, payload sizes, host metrics, billing data, or
in-flight calls.

## 5. Event Trace correlation

`ExtensionTraceStore` supports both generic Extension observations and the
existing `StreamEvent` contract:

```python
trace_store.record(
    "telegram",
    trace_id="trace-1",
    event_id="delivery-1",
    event_type="delivery.sent",
)

trace_store.record_stream_event("pdf-editor", stream_event)
```

One `trace_id` may span multiple Extensions. This allows a future caller to
associate, for example, a PDF Skill event with the Telegram delivery event
that follows it. `trace(trace_id)` returns the shared correlation chain, while
`trace(trace_id, extension_name=...)` and `for_extension(name)` retain strict
per-Extension views.

The Trace Store copies only Stream correlation metadata: stream,
conversation, task, and source identity. It does not publish, reorder, replay,
or validate the Streaming sequence; those responsibilities remain in the
existing Streaming core. An `event_id` must be unique within one Extension,
but different Extensions may use the same provider-local event ID.

## 6. Isolation and concurrency

All three stores protect mutation and snapshot reads with local re-entrant
locks. Keys and histories are partitioned by exact `extension_name`, preventing
Telegram, WeCom, WeChat Customer, PDF Editor, or future Extensions from sharing
counters or history accidentally.

The implementation is process-local and in-memory. It is appropriate for
offline integration tests and a first Extension host. It is not a distributed
metrics backend and does not coordinate multiple QwenPaw Runtime processes.

## 7. Integration policy

This phase deliberately does not wire stores into `SkillInvoker`,
`PluginRuntimeBridge`, Lifecycle Manager, Channel adapters, or Streaming
Dispatcher. Future integration should use composition at the Extension host:

1. invoke the existing Lifecycle, health, Skill, Plugin, or Adapter operation;
2. pass its immutable result to the appropriate observability store;
3. use the existing `trace_id` where one already exists;
4. record exactly one success or failure for each completed call;
5. never include secret values, raw credentials, document content, or Gateway
   database records in observation metadata.

This keeps observability failures from changing business execution semantics.

## 8. Future production backend

A later phase may add exporters or durable storage behind new interfaces for
Prometheus/OpenTelemetry, structured logs, retention, sampling, and cross-host
aggregation. Such exporters must remain optional and must not require changes
to historical Gateway business logic or QwenPaw Runtime core.
