# WeCom Extension Channel Plugin

Official QwenPaw v2.1 Plugin facade for the existing WeCom Extension Adapter.

The entry delegates message conversion and response delivery to
`adapters/wecom/runtime.py`. It does not import, copy, start, or modify the
historical `wecom_bridge.mjs` or `bot.mjs` implementation.

## Boundary

- `plugin.json` maps the internal WeCom Manifest to the official Plugin shape.
- `plugin.py` binds the existing Adapter, Runtime Gateway, Lifecycle, and Health
  bridge using host-injected dependencies.
- Provider credentials are declared by name only; values are not stored here.
- The Node process remains externally supervised and owns provider I/O.

Phase 12.x validates this source-level facade offline. A self-contained official
Plugin ZIP and tenant-compatible `BaseChannel` facade are still required before
live QwenPaw Channel registration.
