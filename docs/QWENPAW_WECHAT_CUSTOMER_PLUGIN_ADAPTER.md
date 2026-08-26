# QwenPaw WeChat Customer Plugin Adapter

> Status: `CUSTOM / TO VERIFY`. This historical open-kfid Gateway chain is not
> equivalent to QwenPaw's built-in 微信 QR-login/Bot Token Channel. Do not add a
> new BaseChannel or deploy this facade until cursor, DB ownership,
> deduplication, session, and rollback semantics are verified.

## Purpose

`plugins/wechat-customer-channel-plugin` exposes the existing WeChat Customer
Extension through the official QwenPaw Plugin facade. It does not replace or
embed the recovered customer-service Gateway.

## Mapping

```text
Official plugin.json / plugin.py
            |
            v
plugins/wechat-customer/manifest.yaml
            |
            v
adapters/wechat_customer/runtime.py
            |
            v
ExtensionRuntimeGateway
```

The official Plugin is identified as `wechat-customer-extension-channel`. Its
internal Extension remains `wechat-customer`, type `plugin`, runtime `python`,
version `0.1.0-recovered`.

## Runtime delegation

The entry constructs the existing `WeChatCustomerRuntimeAdapter` around
host-injected Lifecycle and Gateway Transport objects. The generic Runtime
Wrapper handles Registry lookup, Runtime Gateway receipt, `MessageEvent`
forwarding, response delegation, `DeliveryReceipt`, lifecycle, and health.

## Gateway state boundary

The recovered `plugins/wechat-customer/recovered/wecom_kf_gateway_v345.py`
remains the exclusive owner of:

- provider credentials and API calls;
- SQLite and message-claim state;
- cursor persistence and advancement;
- message deduplication;
- delivery retries.

Only a post-commit event with `cursor_committed=true` and `db_claimed=true` may
cross into the existing Adapter. Cursor values and database handles must never
cross the Plugin facade. The configuration section declares `CORP_ID`,
`APP_SECRET`, `TOKEN`, `AESKEY`, and `OPEN_KFID` names only and stores no values.

## Current acceptance

Offline tests validate Manifest mapping, Registry/Gateway delegation, stable
session mapping behavior, state-ownership metadata, response receipt,
lifecycle/health, Gateway hash preservation, and absence of new database or
cursor files.

Live installation and new Channel development are not authorized in this
phase. First verify whether QwenPaw provides the required open-kfid semantics
and whether Gateway cursor, deduplication, session, database ownership, and
rollback can be preserved. No real WeChat API, secret, Gateway process, or
database is used in this phase.
