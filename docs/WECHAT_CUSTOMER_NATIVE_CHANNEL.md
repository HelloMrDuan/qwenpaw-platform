# WeChat Customer Native QwenPaw Channel

> Phase: 14.0  
> Status: production-candidate Channel package; provider connectivity remains
> unverified  
> Scope: QwenPaw v2.1.0 native Channel registration and offline bridge

## 1. Decision

WeChat Customer is implemented as the single custom messaging Channel retained
by this platform. Telegram, WeCom and ordinary WeChat continue to use QwenPaw
v2.1.0 built-in Channels.

The Plugin registers `WeChatCustomerChannel(BaseChannel)` with the unique key
`wechat_customer`. The key was checked against the v2.1.0 built-in Channel
configuration keys and does not collide with `wechat` or `wecom`.

## 2. Official v2.1.0 contract

The implementation follows the QwenPaw v2.1.0 source contract rather than an
older Plugin example:

- `PluginApi.register_channel(channel_class, label, description,
  config_fields, icon, doc_url)` registers the Channel;
- `BaseChannel.from_config(process, config, on_reply_sent, display_config,
  no_text_debounce)` constructs it (the optional `workspace_dir` accepted by
  the Plugin documentation is also supported);
- `start()` and `stop()` coordinate the external facade;
- `send(to_handle, text, meta)` returns a completed Agent response through the
  existing Adapter and Gateway transport;
- `resolve_session_id()` preserves the existing stable customer identity.

Official source references:

- [BaseChannel v2.1.0](https://github.com/agentscope-ai/QwenPaw/blob/v2.1.0/src/qwenpaw/app/channels/base.py)
- [PluginApi v2.1.0](https://github.com/agentscope-ai/QwenPaw/blob/v2.1.0/src/qwenpaw/plugins/api.py)
- [Plugin system v2.1.0](https://github.com/agentscope-ai/QwenPaw/blob/v2.1.0/website/public/docs/plugins.en.md)

## 3. Runtime chain and ownership

```text
WeChat Customer API
        -> historical Gateway (separate process)
           - provider API and credentials
           - open_kfid / external_userid
           - sync cursor
           - SQLite / atomic msgid claim / deduplication
           - send_msg
        -> compatibility Gateway Facade
        -> existing WeChatCustomerRuntimeAdapter
        -> WeChatCustomerChannel
        -> QwenPaw ChannelManager / Agent
        -> final Agent response
        -> existing Adapter
        -> compatibility Gateway Facade
        -> historical Gateway send_msg
```

The Channel never imports the historical Gateway into the QwenPaw process. It
does not read or write the Gateway database and never receives `cursor` or
`next_cursor`. Only an event marked `cursor_committed=true` and
`db_claimed=true` may pass through the existing Adapter.

The recovered Gateway currently exposes `/healthz` and the provider callback,
but does not expose the bridge endpoints used by the Channel. Production
deployment therefore requires a separately supervised compatibility Facade
that provides `GET /bridge/events` and `POST /bridge/send` without moving
cursor, database or deduplication ownership out of the Gateway. Phase 14 does
not patch the recovered Gateway and does not claim live provider readiness.

## 4. Configuration

Only fields evidenced by the recovered Gateway plus the process boundary are
exposed:

| QwenPaw field | Type | Historical mapping | Purpose |
| --- | --- | --- | --- |
| `corp_id` | text | `CORP_ID` | Enterprise identity |
| `app_secret` | password | `APP_SECRET` | Provider API credential |
| `callback_token` | password | `TOKEN` | Callback signature token |
| `encoding_aes_key` | password | `AESKEY` | Callback encryption key |
| `open_kfid` | text | `OPEN_KFID` | Customer-service account identity |
| `gateway_url` | text | facade address | External process boundary; defaults to local port 8798 |

`app_secret`, `callback_token` and `encoding_aes_key` are the only Plugin
Secret fields. No value or default Secret is present in `plugin.json`, logs or
the release ZIP. `corp_id` and `open_kfid` remain required identities but are
not mislabeled as passwords.

Media directories and a separate health URL are not exposed: the recovered
text-message path does not require a user-configurable media directory, while
health is derived from `gateway_url + /healthz`.

## 5. Session model

The existing Adapter identity is retained without modification:

```text
sha256(open_kfid + NUL + external_userid)
```

The QwenPaw session ID uses that stable identity with the
`ses_wechat_customer_` prefix. The same service/customer pair always resolves
to the same session. A different `open_kfid` or `external_userid` resolves to a
different session, preventing cross-service and cross-customer conversation
leakage.

## 6. Streaming and delivery

QwenPaw may stream internally, but `streaming_enabled` is false for this
Channel. The external path sends an aggregated final response through
`WeChatCustomerRuntimeAdapter.send_response()` and records its
`DeliveryReceipt`. Token-by-token provider streaming is neither simulated nor
claimed.

## 7. Lifecycle and health

QwenPaw owns Plugin enable/disable and calls Channel `start()`/`stop()`.
The Channel coordinates only its polling client; the historical Gateway remains
an independently supervised process.

| Code | Meaning |
| --- | --- |
| `CONFIG_REQUIRED` | At least one required config field is absent |
| `PLUGIN_READY` | Config is complete, Channel is not started |
| `GATEWAY_NOT_RUNNING` | `/healthz` cannot confirm the external Gateway |
| `EXTERNAL_API_UNVERIFIED` | Gateway is reachable but provider API has not been verified |
| `GATEWAY_READY` | Gateway and an injected/deployment probe confirm external readiness |

Missing Secrets can never produce `healthy` or `connected`. The default HTTP
Facade intentionally reports external API verification as false until a real
deployment probe supplies that evidence.

## 8. Offline validation coverage

The Phase 14 tests verify native registration, official BaseChannel method
shape, config typing, session stability and isolation, MessageEvent conversion,
final response delivery, DeliveryReceipt, health mapping, Trace/Metrics, cursor
rejection, state-file non-mutation, historical source hashes, self-contained
ZIP import and process-private namespace isolation. No Secret or external API is
used.

