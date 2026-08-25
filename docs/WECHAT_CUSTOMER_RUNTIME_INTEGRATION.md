# WeChat Customer Gateway Runtime Integration

## 1. Scope

Phase 7.7 places a narrow Extension Runtime boundary around the recovered
WeChat Customer Gateway. It does not replace, import, or start
`plugins/wechat-customer/recovered/wecom_kf_gateway_v345.py`.

```text
WeChat Customer platform
        |
        v
historical Gateway (credentials, callback/sync, DB, cursor)
        |
        | normalized post-commit text event
        v
WeChatCustomerRuntimeAdapter
        |
        v
MessageEvent -> Extension consumer

Extension response
        |
        v
injected Gateway transport facade -> historical Gateway -> provider
```

The QwenPaw/AgentScope Runtime, Agent loop, Message Contract, Streaming core,
and historical Gateway business logic remain outside this change.

## 2. Components

| Component | Responsibility | Explicitly excluded |
| --- | --- | --- |
| `PluginRuntimeBridge` | Discover `wechat-customer`, validate the allowlisted historical entrypoint, map an injected probe to local lifecycle and `HealthReport` | Process launch, HTTP calls, credential access |
| `WeChatCustomerRuntimeAdapter` | Validate a post-commit text event, produce `MessageEvent`, derive a stable session identity | Callback decryption, provider synchronization, cursor or SQLite access |
| `WeChatCustomerGatewayTransport` | Injectable receive/send/health facade for an externally supervised Gateway | A concrete production transport in this phase |
| Historical Gateway | Provider API calls, cursor, deduplication, conversation/session state, response delivery | Extension Registry and Message normalization |

The manifest remains the discovery source. Its current health declaration is
HTTP `http://127.0.0.1:8798/healthz`; offline tests inject a fake probe and do
not connect to that endpoint.

## 3. Inbound event contract

The Adapter accepts only the following credential-free, normalized shape:

```json
{
  "msgid": "provider-message-id",
  "msgtype": "text",
  "origin": 3,
  "external_userid": "provider-customer-id",
  "open_kfid": "provider-service-account-id",
  "text": {"content": "customer text"},
  "gateway_delivery": {
    "delivery_id": "durable-gateway-delivery-id",
    "cursor_committed": true,
    "db_claimed": true
  }
}
```

`origin=3` and `msgtype=text` are mandatory. Raw encrypted callbacks and
non-text messages are not handled in this phase. `cursor` and `next_cursor`
values are rejected at the boundary.

## 4. Cursor non-loss and database ownership

The Gateway is the sole owner of:

- provider cursor loading, advancement, atomic persistence, and retry;
- `processed_messages` claims and message deduplication;
- conversation/session records and delivery status;
- the SQLite connection, schema, WAL files, migrations, and recovery.

The Gateway-facing transport may expose an event only after it can assert both
`cursor_committed=true` and `db_claimed=true`. The Adapter neither receives a
cursor value nor acknowledges advancement. If Extension delivery fails, the
Gateway retries its durable message using the original `msgid`; downstream
consumers should therefore use `msgid` as the idempotency key.

No module under `adapters/wechat_customer/` imports `sqlite3`, opens a Gateway
database, reads a cursor file, or calls a Gateway migration. This preserves the
existing state machine and prevents two writers from competing for state.

## 5. Session mapping

One stable Extension session is derived from both the customer-service account
and the customer identity:

```text
identity = first_24_hex(sha256(open_kfid + NUL + external_userid))
session_id = "ses_wechat_customer_" + identity
conversation_id = "conv_wechat_customer_" + identity
```

Including `open_kfid` prevents one customer contacting different service
accounts from being merged into the same session. Hashing keeps provider IDs
out of the generated session and conversation identifiers. Routing identifiers
remain in `MessageEvent.metadata` only so the injected response facade can
return a reply to the correct Gateway-owned conversation.

This mapping is stateless. It does not replace the Gateway's own session or
conversation records.

## 6. Response and delivery receipt

`send_response()` forwards `external_userid`, `open_kfid`, response text, and
the inbound `msgid` to the injected transport. The transport/Gateway owns the
real provider call and any database update. The Adapter returns a
provider-neutral `DeliveryReceipt` with:

- channel `wechat-customer`;
- the same Extension `session_id`;
- provider message ID returned by the facade, if available;
- `state_owner=gateway` and the original reply target.

The receipt confirms facade acceptance in this offline integration; it is not
proof of end-user delivery unless a future concrete transport supplies that
provider guarantee.

## 7. Health and lifecycle synchronization

The Registry discovers `plugins/wechat-customer/manifest.yaml`. The Plugin
Runtime Bridge permits only the recovered Python entrypoint declared by that
manifest. An injected `ExternalServiceProbe` produces a credential-free
snapshot:

- reachable `RUNNING` moves the local simulated lifecycle to `RUNNING`;
- `STOPPED` moves a simulated running record back to `ENABLED`;
- unknown, failed, or unreachable states produce an unhealthy `HealthReport`.

These transitions describe the observed external service. They do not start,
stop, or modify the historical Gateway.

## 8. Offline verification

`tests/runtime/test_wechat_customer_runtime.py` uses a fake transport and a
temporary deployment directory. It verifies:

- manifest discovery and allowlisted historical entrypoint;
- Gateway health reporting and lifecycle synchronization;
- deterministic account-scoped session mapping;
- text conversion and response `DeliveryReceipt`;
- rejection of uncommitted, unclaimed, or cursor-bearing events;
- unchanged historical Gateway hash and absence of new DB/cursor files.

No real Gateway, provider API, secret, database, or cursor file is accessed.

## 9. Deferred production work

A later, separately reviewed phase may implement a supervised IPC/HTTP
transport between the historical Gateway and this facade. That work must first
define durable post-commit delivery and idempotent retry without changing the
Gateway's DB/cursor ownership. Direct import of the recovered module remains
forbidden because its top-level initialization depends on runtime credentials.
