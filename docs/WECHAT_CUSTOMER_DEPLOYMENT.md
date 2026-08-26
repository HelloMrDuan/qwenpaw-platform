# WeChat Customer Channel Deployment

> Target: QwenPaw v2.1.0  
> Package: `wechat-customer-extension-channel-v0.1.0-recovered.zip`

## 1. Deployment topology

Deploy the QwenPaw Plugin and historical Gateway as separate runtime units:

```text
QwenPaw v2.1.0 process
  └─ wechat_customer Channel Plugin
       └─ HTTP Gateway Facade client

separately supervised Gateway unit
  ├─ compatibility Facade
  └─ recovered wecom_kf_gateway_v345.py
       ├─ SQLite/WAL
       ├─ sync_cursor_v345.json
       └─ WeChat Customer API
```

Do not copy the Gateway database or cursor into the Plugin directory. Do not
start the recovered Gateway by importing it from `plugin.py`.

## 2. Build and install

Build the candidate from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\build_extension.py `
  --qwenpaw-plugin wechat-customer-channel-plugin `
  --output dist\extensions
```

Install the generated ZIP through QwenPaw Plugin Management while following the
v2.1.0 operational rule for Plugin installation/restart. After installation,
the Plugin must appear as a Channel registration with key
`wechat_customer`.

The ZIP is self-contained for Python imports. Its private package namespace
contains the native Channel, Gateway facade client, existing Adapter, contracts
and required Extension runtime modules. It does not bundle credentials,
Gateway databases, cursor files, caches or logs.

## 3. Configuration and Secret injection

Configure these values in the QwenPaw Channel settings; never bake them into
the ZIP:

| QwenPaw setting | Required | Secret | Gateway destination |
| --- | ---: | ---: | --- |
| `corp_id` | yes | no | `CORP_ID` |
| `app_secret` | yes | yes | `APP_SECRET` |
| `callback_token` | yes | yes | `TOKEN` |
| `encoding_aes_key` | yes | yes | `AESKEY` |
| `open_kfid` | yes | no | `OPEN_KFID` |
| `gateway_url` | yes | no | Compatibility Facade base URL |

The Plugin manifest records this name mapping for packaging validation. Secret
transfer to the independently supervised Gateway is a deployment concern; the
Channel object retains only which required fields were provided and does not
retain or log their values.

## 4. Gateway compatibility prerequisite

Before enabling the Channel, the independently deployed compatibility Facade
must provide:

- `GET /healthz`: Gateway process health;
- `GET /bridge/events`: one normalized, already cursor-committed and
  DB-claimed event, or HTTP 204;
- `POST /bridge/send`: delegate a final text response to Gateway `send_msg` and
  return `{ "accepted": true, "provider_message_id": "..." }`.

The recovered `wecom_kf_gateway_v345.py` does not yet expose the latter two
endpoints. A deployment must not claim `GATEWAY_READY` until this facade exists
and the real provider probe has passed. The facade must not independently read,
advance or reset the cursor, and must not implement a second deduplication
database.

## 5. Start order

1. Back up Gateway DB and cursor using the Gateway's established operational
   procedure.
2. Start the recovered Gateway under its existing supervisor.
3. Start the compatibility Facade and verify `/healthz` locally.
4. Install the QwenPaw Plugin ZIP.
5. Inject config and Secrets through the QwenPaw configuration surface.
6. Enable the `wechat_customer` Channel.
7. Confirm health progresses from `PLUGIN_READY` to
   `EXTERNAL_API_UNVERIFIED`; only a real staging provider probe may establish
   `GATEWAY_READY`.
8. Run a staging message and confirm stable session, one DB claim, one Agent
   invocation and one provider delivery before production rollout.

## 6. Rollback

1. Disable the `wechat_customer` Channel so no new Agent work is accepted.
2. Stop the compatibility Facade client/sidecar, leaving Gateway persistence
   intact.
3. Roll back or uninstall only the Plugin version.
4. Do not rewind `sync_cursor_v345.json`, restore an older live DB over the
   current DB, or clear deduplication records merely to roll back the Plugin.
5. Re-enable the prior known-good path only after checking for messages already
   claimed or delivered.

Plugin rollback and Gateway state rollback are deliberately separate. Cursor
rewind can duplicate customer messages and is not part of this release process.

## 7. Acceptance gates

- Plugin ZIP integrity and SHA256 recorded;
- isolated `plugin.py` import passes without repository `PYTHONPATH`;
- `PluginApi.register_channel()` registers `WeChatCustomerChannel`;
- Channel key does not collide with v2.1.0 built-ins;
- no Secret value, DB, cursor, log or cache in the ZIP;
- recovered Gateway and existing Adapter SHA256 unchanged;
- full offline test suite passes;
- staging Facade and provider tests pass before production enablement.

Phase 14 completes the code and offline-package gates only. It does not connect
to WeChat Customer, install into a tenant, or certify the missing compatibility
Facade deployment.

