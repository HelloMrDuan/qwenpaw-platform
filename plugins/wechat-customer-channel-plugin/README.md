# WeChat Customer Extension Channel Plugin

Official QwenPaw v2.1 Plugin facade for the existing WeChat Customer Adapter.

The entry delegates to `adapters/wechat_customer/runtime.py`. It does not
import, copy, start, or modify `wecom_kf_gateway_v345.py`.

## State ownership boundary

- The historical Gateway exclusively owns credentials, provider API calls,
  SQLite data, cursor persistence, message claiming, and deduplication.
- Only post-commit Gateway events may cross into the existing Adapter.
- `plugin.py` binds the Adapter, Runtime Gateway, Lifecycle, and Health bridge
  using host-injected dependencies.
- `plugin.json` declares secret names only and contains no values.

Phase 12.6 uses `scripts/build_extension.py --qwenpaw-plugin
wechat-customer-channel-plugin` to generate a self-contained official Plugin
ZIP. A tenant-compatible `BaseChannel` facade and real QwenPaw installation
validation are still required before live Channel registration.
