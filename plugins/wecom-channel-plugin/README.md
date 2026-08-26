# WeCom Extension Channel Plugin

> Status: `LEGACY / FALLBACK / REFERENCE ONLY`. Production uses the QwenPaw
> v2.1.0 built-in WeCom Channel. Do not add a custom WeCom `BaseChannel` or
> `register_channel()` implementation here.

Historical packaging facade for the existing WeCom Extension Adapter.

The entry delegates message conversion and response delivery to
`adapters/wecom/runtime.py`. It does not import, copy, start, or modify the
historical `wecom_bridge.mjs` or `bot.mjs` implementation.

## Boundary

- `plugin.json` maps the internal WeCom Manifest to the official Plugin shape.
- `plugin.py` binds the existing Adapter, Runtime Gateway, Lifecycle, and Health
  bridge using host-injected dependencies.
- Provider credentials are declared by name only; values are not stored here.
- The Node process remains externally supervised and owns provider I/O.

Phase 12.6 used `scripts/build_extension.py --qwenpaw-plugin
wecom-channel-plugin` to validate self-contained packaging. That artifact is a
fallback/reference package, not a production Channel candidate. Custom WeCom
Channel registration work is closed; configure and validate the built-in
Channel instead.
