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

Phase 12.6 uses `scripts/build_extension.py --qwenpaw-plugin
wecom-channel-plugin` to generate a self-contained official Plugin ZIP. A
tenant-compatible `BaseChannel` facade and real QwenPaw installation validation
are still required before live Channel registration.
