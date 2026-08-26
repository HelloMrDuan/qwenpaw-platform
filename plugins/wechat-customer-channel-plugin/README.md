# WeChat Customer Native Channel Plugin

Production strategy: `CUSTOM REQUIRED`. This Plugin registers the unique
`wechat_customer` Channel through QwenPaw v2.1.0 `PluginApi.register_channel`.

The entry delegates to `adapters/wechat_customer/runtime.py`. It does not import,
start, or modify `wecom_kf_gateway_v345.py` in the QwenPaw process.

## State ownership boundary

- The historical Gateway exclusively owns credentials, provider API calls,
  SQLite data, cursor persistence, message claiming, and deduplication.
- Only post-commit Gateway events may cross into the existing Adapter.
- `channel.py` implements the official `BaseChannel` contract and aggregates
  internal streaming into completed external replies.
- `gateway_facade.py` coordinates an independently supervised Gateway process.
- `plugin.json` declares password fields but contains no Secret values.

## Facade endpoints

The compatibility facade is expected at `gateway_url` and exposes:

- `GET /healthz`;
- `GET /bridge/events` for already cursor-committed and DB-claimed events;
- `POST /bridge/send` to delegate final/segmented outbound delivery.

Phase 14.0 uses `scripts/build_extension.py --qwenpaw-plugin
wechat-customer-channel-plugin` to generate a self-contained official Plugin
ZIP with a process-private Python namespace. Real facade and provider API
validation remain deployment-stage operations.
