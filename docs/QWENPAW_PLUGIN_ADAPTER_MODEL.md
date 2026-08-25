# QwenPaw Official Plugin Adapter Model

## 1. Purpose

Phase 12 adds a compatibility facade between this repository's internal
Extension model and the QwenPaw v2.1 official Plugin contract. It does not
replace AgentScope/QwenPaw Runtime, implement a provider Channel, or change any
recovered business component.

The first adapter set targets the existing Telegram, WeCom, and WeChat
Customer Adapters:

```text
QwenPaw Plugin package
  plugin.json
  plugin.py
        |
        v
Internal Extension Registry ---- adapters/telegram/manifest.yaml
        |
        v
ExtensionRuntimeGateway -------- adapters/telegram/runtime.py
        |
        +---- MessageEvent in
        +---- DeliveryReceipt out
        +---- Lifecycle/Health synchronization
```

The recovered Telegram Bridge, WeCom Node Bridge, and WeChat Customer Gateway
remain the provider implementations. The official facades neither import nor
copy them.

## 2. Manifest mapping

QwenPaw's official backend Plugin package uses `plugin.json` and a backend
entry declared by `entry.backend`. The adapter keeps the official fields at the
top level and stores repository-specific information inside the free-form
`meta` object.

| Official Plugin field | Internal source | Rule |
| --- | --- | --- |
| `id` | Release definition | Stable lowercase kebab-case identifier |
| `name` | Release definition | Display name |
| `version` | Extension Manifest | Must match the Extension version |
| `type` | Adapter mapping | Telegram is published as `channel` |
| `description` | Release definition | Describes the facade, not a new Bridge |
| `entry.backend` | Wrapper package | `plugin.py` |
| `dependencies` | Release definition | Explicit package dependencies only |
| `qwenpaw_version` | Release policy | Supported tenant version range |
| `meta.extension` | Extension Manifest | Internal name, type, runtime and paths |
| `meta.permissions` | Wrapper policy | Declared capabilities, no credentials |
| `meta.config` | Wrapper policy | Configuration schema and empty values |
| `meta.required_secrets` | Extension Manifest | Secret names only |

`plugins/runtime-wrapper/manifest_template.py` validates the internal Manifest
before generating this mapping. A generated document is compared byte-for-data
with the checked-in Telegram `plugin.json` by the offline contract test.

## 3. Runtime responsibilities

### Generic Runtime wrapper

`OfficialPluginRuntimeWrapper` is provider-neutral and only:

- discovers and validates one internal Extension;
- binds an already-created Adapter and `ExtensionRuntimeGateway`;
- receives normalized `MessageEvent` objects through the Gateway;
- forwards an event to a host-injected handler;
- delegates outbound response conversion to the existing Adapter;
- mirrors allowed lifecycle actions through an injected lifecycle manager.

It does not import QwenPaw, start a process, perform network access, or read
secret values.

### Channel Plugin entries

Each Channel Plugin entry constructs its existing Runtime Adapter,
`PluginRuntimeBridge`, and `ExtensionRuntimeGateway` around dependencies
supplied by the host or test harness. Provider parsing, session mapping,
response conversion, health probing, and delivery receipts stay in the
existing Adapter.

| Official facade | Existing Adapter | Historical implementation retained |
| --- | --- | --- |
| `telegram-channel-plugin` | `adapters/telegram/runtime.py` | Telegram Bridge |
| `wecom-channel-plugin` | `adapters/wecom/runtime.py` | `wecom_bridge.mjs` |
| `wechat-customer-channel-plugin` | `adapters/wechat_customer/runtime.py` | `wecom_kf_gateway_v345.py` |

The official `register(api)` entry currently registers a process-safe startup
hook that validates Extension metadata. Live `api.register_channel(...)`
activation is intentionally deferred until a supervised Telegram transport and
a tenant-version-compatible QwenPaw Channel facade is available. This phase
therefore proves the packaging and delegation contract, not external service
connectivity.

## 4. Message and lifecycle flow

```text
Provider update (injected/offline in Phase 12)
        |
        v
Existing TelegramRuntimeAdapter
        |
        v
ExtensionRuntimeGateway.receive_message()
        |
        v
MessageEvent -> QwenPaw-side injected handler
        |
        v
Existing Adapter.send_response()
        |
        v
DeliveryReceipt
```

Lifecycle synchronization is limited to `verify`, `enable`, `disable`, `start`,
`stop`, `health`, and `rollback`. The wrapper delegates those operations; it
does not directly supervise the recovered process.

## 5. Security and packaging rules

- Never place token, secret, credential, `.env`, database, log, or cache values
  in `plugin.json` or the Plugin archive.
- Configuration declarations may contain required secret names, but their
  values must be injected by QwenPaw or the deployment environment.
- The official archive must include the facade plus the generic wrapper and all
  required repository modules; a source directory that relies on repository
  imports is not yet a standalone upload artifact.
- Packaging must preserve the original Extension Manifest version and reject
  missing internal entry paths.
- Installation, tenant upload, real Telegram API access, and recovered Bridge
  startup remain outside the Phase 12 offline test boundary.

## 6. Acceptance boundary

Phase 12 is accepted when:

1. `plugin.json` matches the official Plugin field contract;
2. `plugin.py` exists and exposes a registration entry;
3. the internal Extension Registry discovers Telegram;
4. the existing Telegram Adapter loads without importing recovered Bridge code;
5. simulated messages traverse the Runtime Gateway and return a
   `DeliveryReceipt`;
6. historical Telegram source hashes remain unchanged;
7. all repository tests pass offline.

A later packaging phase is required before tenant upload: it must build a
self-contained official Plugin ZIP and validate the concrete QwenPaw
`PluginApi`/Channel API for the target tenant without changing recovered
Telegram business logic.

## 7. Official references

- [QwenPaw Plugin System](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md)
- [QwenPaw contributing guide: adding channels](https://github.com/agentscope-ai/QwenPaw/blob/main/CONTRIBUTING.md#adding-new-channels)
