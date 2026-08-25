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

Phase 12.x validates this source-level facade offline. A self-contained official
Plugin ZIP and tenant-compatible `BaseChannel` facade are still required before
live QwenPaw Channel registration.
