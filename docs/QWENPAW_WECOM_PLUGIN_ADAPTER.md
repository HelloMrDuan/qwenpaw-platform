# QwenPaw WeCom Plugin Adapter

> Status: `LEGACY / FALLBACK / REFERENCE ONLY`. Production uses the QwenPaw
> v2.1.0 built-in 企业微信 Channel. Custom WeCom `BaseChannel` and Channel
> registration development is stopped.

## Purpose

`plugins/wecom-channel-plugin` exposes the recovered WeCom Extension through
the same official QwenPaw Plugin facade established for Telegram. This is an
offline packaging and delegation layer, not a replacement WeCom Channel.

## Mapping

```text
Official plugin.json / plugin.py
            |
            v
plugins/wecom/manifest.yaml
            |
            v
adapters/wecom/runtime.py
            |
            v
ExtensionRuntimeGateway
```

The official Plugin is identified as `wecom-extension-channel`. Its internal
Extension remains `wecom`, type `plugin`, runtime `node`, version
`0.1.0-recovered`.

## Runtime delegation

The entry constructs the existing `WeComRuntimeAdapter` using injected
Lifecycle and Transport objects. The generic Runtime Wrapper then:

- discovers WeCom through `ExtensionRegistry`;
- receives normalized `MessageEvent` through `ExtensionRuntimeGateway`;
- forwards the event to a host-injected handler;
- delegates response conversion to `WeComRuntimeAdapter.send_response()`;
- returns the existing `DeliveryReceipt`;
- synchronizes health and lifecycle through `PluginRuntimeBridge`.

## Historical boundary

The following files remain unchanged and externally supervised:

- `plugins/wecom/recovered/wecom-node/wecom_bridge.mjs`;
- `plugins/wecom/recovered/wecom-node/bot.mjs`.

The facade does not import or start Node, call the WeCom API, use credentials,
or reproduce Bridge logic. `WECOM_BOT_ID`, `WECOM_BOT_SECRET`, and `SN_API_KEY`
are configuration names only; `plugin.json` contains no values.

## Current acceptance

Offline tests validate official Manifest generation, Plugin entry loading,
Registry discovery, Runtime Gateway message flow, response receipt, health,
lifecycle, and historical-file hashes.

Live installation is not planned. The self-contained ZIP and offline tests are
retained as fallback/reference evidence; production staging must validate the
built-in 企业微信 Channel instead.
