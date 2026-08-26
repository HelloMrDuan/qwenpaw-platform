# WeChat Customer Fit-Gap Analysis

> Phase: 13.0  
> Decision: `CUSTOM REQUIRED` to preserve the historical WeChat Customer business chain  
> Scope: repository and exported-configuration audit only; no external API was called.

## 1. Executive conclusion

QwenPaw v2.1.0 provides built-in `WeChat` and `WeCom` Channels, but the current
tenant Console evidence and exported configuration do not expose the historical
WeChat Customer (`微信客服`) semantics. The built-in entries are not evidence of
support for `open_kfid`, customer-message synchronization, cursor ownership,
`external_userid`, Customer Service `send_msg`, Gateway persistence, or durable
deduplication.

To preserve the existing customer-service workflow, WeChat Customer is therefore
`CUSTOM REQUIRED`. This is an architecture classification, not authorization to
create a `BaseChannel`, Plugin, Gateway replacement, or production connection.

## 2. Historical business chain

```text
WeChat Customer event/callback
        -> open_kfid tenant/service identity
        -> external_userid customer identity
        -> /cgi-bin/kf/sync_msg + cursor
        -> historical Gateway on port 8798
        -> Gateway-owned SQLite state and atomic deduplication
        -> adapters/wechat_customer/runtime.py
        -> MessageEvent / Agent boundary
        -> Gateway-owned /cgi-bin/kf/send_msg delivery
```

The historical Gateway and the Extension Adapter deliberately have different
state ownership:

- Gateway owns provider credentials, callback verification, cursor persistence,
  SQLite, deduplication, delivery calls, and retry/status state;
- Adapter accepts only a normalized post-commit event, rejects cursor fields,
  maps `open_kfid + external_userid` to a stable session, and returns delivery
  through an injected Gateway facade;
- the Agent/Extension layer must not open or migrate the Gateway database.

## 3. Source evidence

| Requirement | Historical implementation evidence | Current status |
| --- | --- | --- |
| `open_kfid` | Gateway filters callback and synchronized messages by `OPEN_KFID`; Adapter uses it as tenant identity | Present in custom chain |
| `external_userid` | Gateway uses it for customer identity/history/delivery; Adapter includes it in identity mapping | Present in custom chain |
| Customer message pull | Gateway calls `/cgi-bin/kf/sync_msg` from callback processing and a polling fallback | Present in custom chain |
| Cursor persistence | `sync_cursor_v345.json` is atomically replaced after polling advances `next_cursor` | Present in custom chain; historical cursor data itself was not recovered |
| Callback Gateway | HTTP callback verification/decryption and `/healthz` on port 8798 | Present in recovered source |
| Database ownership | SQLite WAL database with `processed_messages`, `conversation_messages`, and `generated_images` schemas | Present in recovered source; historical DB file was intentionally not migrated |
| Deduplication | `msgid` primary key, status checks, and `INSERT OR IGNORE` atomic claim | Present in custom chain |
| Customer delivery | `/cgi-bin/kf/send_msg` for text and image messages | Present in custom chain |
| Session mapping | Adapter hashes `open_kfid + NUL + external_userid` into stable session/conversation/user identifiers | Present in Extension boundary |
| Cursor isolation | Adapter rejects `cursor` and `next_cursor`, and requires proof that the Gateway committed cursor and DB claim first | Present in Extension boundary |

Evidence paths:

- `plugins/wechat-customer/recovered/wecom_kf_gateway_v345.py`
- `plugins/wechat-customer/README.md`
- `plugins/wechat-customer/manifest.yaml`
- `adapters/wechat_customer/runtime.py`

## 4. Comparison with QwenPaw v2.1.0 built-ins

The comparison uses the verified Console capability and exported
`configs/agent.json` key names only. Configuration values and Secrets were not
read or reported.

| Required WeChat Customer semantic | Built-in `wechat` evidence | Built-in `wecom` evidence | Finding |
| --- | --- | --- | --- |
| `open_kfid` | No exported key | No exported key | Not evidenced |
| `external_userid` | No exported key | No exported key | Not evidenced |
| `/cgi-bin/kf/sync_msg` pull | No exported key or repository entry | No exported key or repository entry | Not evidenced |
| Durable cursor/`next_cursor` | No exported key | No exported key | Not evidenced |
| Customer Service `/cgi-bin/kf/send_msg` | No exported key or built-in contract evidence | No exported key or built-in contract evidence | Not evidenced |
| Customer callback Gateway | Built-in uses Bot Token/base URL and message merge settings | Built-in uses Bot ID/Secret/WebSocket settings | Different integration model |
| Gateway-owned DB | No exported DB/state-ownership setting | No exported DB/state-ownership setting | Not evidenced |
| Durable `msgid` deduplication | No exported setting or contract evidence | No exported setting or contract evidence | Not evidenced |

Relevant exported built-in shapes are:

- `channels.wechat`: Bot Token/token file, base URL, and message-merge settings;
- `channels.wecom`: Bot ID, Secret, WebSocket URL, welcome/group-context,
  reconnect, and streaming settings.

These shapes establish that QwenPaw has built-in WeChat and WeCom Channels. They
do not establish functional equivalence with the WeChat Customer open-kfid API.

## 5. Fit-gap decision

| Question | Decision |
| --- | --- |
| Can built-in WeChat replace the historical customer-service chain? | No evidence of equivalence |
| Can built-in WeCom replace it? | No evidence of open-kfid/cursor/customer-service semantics |
| Is a custom implementation still required to preserve the workflow? | Yes: `CUSTOM REQUIRED` |
| Should a new `BaseChannel` or Plugin be developed now? | No; prohibited in this phase |
| Who owns cursor and DB if work resumes later? | The external Gateway exclusively |
| May the Adapter receive or persist cursor state? | No |

This conclusion is scoped to QwenPaw v2.1.0 and the currently verified tenant
surfaces. If a later official, documented open-kfid Channel appears, the decision
must be re-evaluated with cursor, deduplication, state migration, delivery, and
rollback tests before replacing the custom chain.

## 6. Missing runtime assets and risks

The recovered source proves the protocol and state model, but it is not currently
ready for production deployment:

- `sn_agent_runner.py` is not recovered;
- the historical database and cursor file are intentionally absent;
- no sanitized configuration template or locked dependency snapshot exists;
- only text messages cross the current Adapter boundary;
- no live provider, Secret, callback, or staging validation was performed here.

`CUSTOM REQUIRED` means “a distinct custom boundary is necessary if this
business capability is retained”; it does not mean the recovered Gateway is
already production-ready.

## 7. Constraints for any future implementation phase

Any future phase must preserve these invariants:

1. Gateway is the exclusive owner of provider Secrets, cursor and SQLite;
2. cursor is durable before an event crosses into Extension Runtime;
3. `msgid` is atomically claimed before Agent invocation;
4. session identity includes both `open_kfid` and `external_userid`;
5. rollback cannot rewind cursor or cause duplicate delivery;
6. no custom BaseChannel work starts without explicit authorization.

No implementation is authorized by this document.
