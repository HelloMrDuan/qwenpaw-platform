# AgentScope/QwenPaw Plugin Installation Validation

> **Strategy status:** Telegram and WeCom packages in this report are
> `LEGACY / FALLBACK / REFERENCE ONLY`. QwenPaw v2.1.0 built-in Channels are the
> production default. No Telegram/WeCom `BaseChannel`, custom Channel
> registration, or production reinstall is planned. WeChat Customer remains
> `CUSTOM / TO VERIFY`. See `QWENPAW_CHANNEL_STRATEGY.md`.

> Historical Phase 12.5 record. Its three-file candidate ZIPs were superseded
> by the self-contained Phase 12.6 packages documented in
> `docs/PLUGIN_SELF_CONTAINED_MODEL.md`; the hashes below remain the evidence for
> the earlier failed candidates.

## 1. Validation scope

- Date: 2026-08-25
- Repository baseline: `5fa1985df7d1877bd90dd001e0207bce7c3bf79e`
- Target: QwenPaw v2.1 official backend Channel Plugin contract
- Mode: local, offline, no credentials, no external service, no historical
  process startup

Validated source facades:

- `plugins/telegram-channel-plugin`
- `plugins/wecom-channel-plugin`
- `plugins/wechat-customer-channel-plugin`

This validation distinguishes three different claims:

1. **Manifest contract**: `plugin.json` uses the official field shape.
2. **Archive contract**: required files exist at the ZIP root and can be read.
3. **Runtime installability**: QwenPaw can install, import, register, and run the
   Plugin in an isolated Runtime.

Passing the first two does not imply the third.

## 2. Official installation contract

The official QwenPaw Plugin documentation defines a backend Plugin with at
least:

```text
plugin root/
├── plugin.json
├── plugin.py
└── README.md  # recommended
```

`plugin.json` must identify the Plugin and point `entry.backend` to the Python
entry that exports `plugin`. `channel` is the official type for a custom
messaging Channel. `qwenpaw_version.min` is inclusive and `max` is exclusive.

Officially documented installation paths include:

```text
qwenpaw plugin install /path/to/plugin
qwenpaw plugin install https://example.com/plugin.zip
```

The current QwenPaw v2.1 tenant UI previously observed for this project also
offers folder/ZIP upload and URL installation. The official CLI documentation
requires Plugin management operations to be performed while QwenPaw is
offline.

Reference:

- [QwenPaw Plugin System](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md)

## 3. Generated candidate packages

Three independent candidate packages were generated under the Git-ignored
directory `dist/extensions/qwenpaw-plugins/`:

| Package | Size | SHA256 |
| --- | ---: | --- |
| `telegram-extension-channel-v0.1.0-recovered.zip` | 2,822 bytes | `43c4d6ae484469f0f9e4e278e87a0331b6b0616b086e2bda72d7aacc7ad74988` |
| `wecom-extension-channel-v0.1.0-recovered.zip` | 2,649 bytes | `077d968dbf377ea0b822c3d0f3e2869dc012150b74608aa2124368f19e957f50` |
| `wechat-customer-extension-channel-v0.1.0-recovered.zip` | 2,720 bytes | `55a6a8854713599b065e9d0a286b7038d4289152b8e207c5ef37308d5aef0789` |

Each ZIP currently contains exactly:

```text
plugin.json
plugin.py
README.md
```

The files are at the archive root, all ZIPs open successfully, and their hashes
were calculated after packaging. They are local validation artifacts and are
not committed as source files.

## 4. Static validation results

| Check | Telegram | WeCom | WeChat Customer | Result meaning |
| --- | --- | --- | --- | --- |
| ZIP integrity/readability | PASS | PASS | PASS | Archive can be opened and enumerated |
| Root `plugin.json` | PASS | PASS | PASS | Official manifest is present |
| Root `plugin.py` | PASS | PASS | PASS | Declared backend entry exists |
| `entry.backend=plugin.py` | PASS | PASS | PASS | Entry path resolves inside the ZIP |
| `type=channel` | PASS | PASS | PASS | Official Channel type |
| Version syntax | PASS | PASS | PASS | `0.1.0-recovered` is a SemVer prerelease |
| QwenPaw version range | PASS | PASS | PASS | `>=2.1.0,<2.2.0` |
| Permission list | PASS | PASS | PASS | Non-empty and duplicate-free |
| Config values empty | PASS | PASS | PASS | Only field/secret names are declared |
| Internal Manifest exists in repository | PASS | PASS | PASS | Referenced source Manifest is available locally |
| Internal Manifest bundled in ZIP | FAIL | FAIL | FAIL | Repository Extension metadata is absent from the archive |
| Isolated `plugin.py` import | FAIL | FAIL | FAIL | `ModuleNotFoundError: No module named 'adapters'` |

### Manifest distinction

The official Plugin Manifest is `plugin.json`; it is present and structurally
valid in all three archives. Each Plugin also references an internal Extension
`manifest.yaml` under `meta.extension.manifest`. QwenPaw does not require that
internal Manifest, but this repository's `OfficialPluginRuntimeWrapper` does.
The internal Manifest is available in the source repository but is not included
in the current ZIPs.

### Permission distinction

`meta.permissions` is syntactically valid repository policy metadata. QwenPaw
defines `meta` as free-form data; this validation does not claim that QwenPaw
enforces these permission strings as a security sandbox.

## 5. Self-contained Runtime probe

Each ZIP was extracted to a new temporary directory and its `plugin.py` was
started with Python isolated mode. No repository path was added to `sys.path`.
All three entries failed before registration with:

```text
ModuleNotFoundError: No module named 'adapters'
```

This is expected from the current source-level facade. The entries depend on:

- `adapters/<channel>/runtime.py`;
- `core/contracts`;
- `core/extensions` and `core/extensions/runtime`;
- `core/streaming`;
- `plugins/runtime-wrapper/runtime.py`;
- the corresponding internal Extension Manifest.

Those modules are not bundled. The current `plugin.py` files also derive a
repository root from their source-tree position, so copying only the three
Plugin files into QwenPaw cannot reproduce the repository layout.

In addition, the entries currently register a safe startup metadata hook. They
do not yet register a QwenPaw `BaseChannel` subclass through
`PluginApi.register_channel(...)`. Consequently a successful file installation
would not yet create an operational Channel card.

## 6. Local Runtime environment result

Environment probe:

| Item | Result |
| --- | --- |
| Python | `3.11.8` |
| `qwenpaw` command | NOT FOUND |
| `agentscope` command | NOT FOUND |
| `qwenpaw` Python package | NOT INSTALLED |
| `agentscope` Python package | NOT INSTALLED |

No local AgentScope/QwenPaw Plugin installer or disposable Runtime is available.
No cloud tenant upload was authorized or attempted.

**RUNTIME INSTALL NOT EXECUTED**

## 7. Current validation status

| Layer | Status | Conclusion |
| --- | --- | --- |
| Source Plugin facade tests | PASS | Existing Registry/Gateway/Adapter delegation works offline |
| Official Manifest shape | PASS | Required fields and entry mapping are valid |
| Candidate ZIP structure | PASS | Official minimum root files exist |
| Secret-value exclusion | PASS | No credential value is included |
| Self-contained package | FAIL | Internal repository modules and Manifest are missing |
| QwenPaw Channel registration | NOT READY | No tenant-compatible `BaseChannel` facade is registered |
| Official Runtime installation | NOT EXECUTED | No local Runtime environment exists |

Overall status: **STRUCTURE VALIDATED / RUNTIME PACKAGE NOT READY**.

The three ZIPs must not be uploaded as production Plugins in their current
form. Their hashes document the artifacts that were inspected; they are not a
release approval.

## 8. Difference from AgentScope Skill installation

| Aspect | AgentScope Skill | QwenPaw Plugin |
| --- | --- | --- |
| Primary descriptor | Skill descriptor/Manifest | `plugin.json` |
| Runtime entry | Skill executor invoked by Agent | `plugin.py` loaded by QwenPaw Plugin Runtime |
| Installation surface | Skill center/workspace Skill upload | Plugin manager: directory, ZIP/URL depending on surface |
| Execution scope | Tool/Skill invocation | Code can register Runtime hooks, Channels, APIs, providers or tools |
| Channel requirement | Not applicable | Must register a compatible `BaseChannel` implementation |
| Dependency risk | Skill executor dependencies | Plugin code executes in the QwenPaw process and has broader impact |
| Current project evidence | PDF Editor uploaded and executed successfully | Static ZIP validation only; Runtime install not executed |

The successful PDF Editor Skill validation therefore does not prove Plugin ZIP
compatibility. Plugin installation requires a separate package, import,
registration, lifecycle, uninstall, and rollback acceptance process.

## 9. Superseded implementation direction

The earlier plan to add Telegram and WeCom `BaseChannel` facades and validate
`PluginApi.register_channel(...)` is cancelled. Package and import records are
retained as historical engineering evidence only. Production validation moves
to the built-in Channel configuration surface. WeChat Customer must be assessed
separately because its Gateway/cursor/database semantics are not equivalent to
the built-in 微信 login model.

## 10. Phase 12.7 real QwenPaw v2.1.0 feedback

The following results supersede the earlier `RUNTIME INSTALL NOT EXECUTED`
statement for these exact Phase 12.6 candidates. They were supplied from a real
AgentScope/QwenPaw v2.1.0 tenant on 2026-08-26:

| Plugin | Real installation | Runtime status | Evidence |
| --- | --- | --- | --- |
| Telegram | **REAL INSTALL PASS** | **STATUS RUNNING** | Installed package is visible in the Plugin list |
| WeCom | **REAL INSTALL FAIL** | Not started | `No module named 'adapter.wecom'` |
| WeChat Customer | **REAL INSTALL FAIL** | Not started | `No module named 'adapter.wechat_customer'` |

No secret, external API call, historical Bridge startup, or Gateway startup was
used by the local namespace investigation.

## 11. Phase 12.6 ZIP comparison and root cause

The three Phase 12.6 ZIPs were opened and fully enumerated before rebuilding the
failed artifacts. All three contained `adapter/__init__.py`, the exact Python
module directory, its `__init__.py`, and `runtime.py`. In particular, WeChat
Customer used the correct underscore module name `wechat_customer`, not the
release-name spelling `wechat-customer`.

The decisive reproduction loaded the three entries sequentially in one Python
interpreter. Telegram passed, then WeCom and WeChat Customer failed with the
same two QwenPaw errors. After Telegram loaded, `sys.modules['adapter'].__path__`
contained only Telegram's extracted `adapter/` directory. Python reuses a
cached regular package before considering later `sys.path` entries, so each
later `sys.path.insert` could not change where `adapter.<channel>` was searched.

Therefore the root cause was a **process-global top-level Python package
collision**, not directory flattening, a missing `__init__.py`, a channel-name
conversion, or an absent Adapter source.

### 11.1 Telegram candidate tree (installed successfully)

```text
README.md
adapter/__init__.py
adapter/telegram/__init__.py
adapter/telegram/runtime.py
adapters/telegram/manifest.yaml
adapters/telegram/recovered/telegram_bridge_main.py
contracts/__init__.py
contracts/artifact.py
contracts/channel.py
contracts/message.py
contracts/skill.py
contracts/stream_consumer.py
contracts/stream_renderer.py
contracts/streaming.py
core/__init__.py
core/contracts/__init__.py
core/contracts/artifact.py
core/contracts/channel.py
core/contracts/message.py
core/contracts/skill.py
core/contracts/stream_consumer.py
core/contracts/stream_renderer.py
core/contracts/streaming.py
core/extensions/README.md
core/extensions/__init__.py
core/extensions/lifecycle/__init__.py
core/extensions/lifecycle/health.py
core/extensions/lifecycle/manager.py
core/extensions/lifecycle/models.py
core/extensions/loader.py
core/extensions/models.py
core/extensions/observability/__init__.py
core/extensions/observability/health_store.py
core/extensions/observability/metrics.py
core/extensions/observability/models.py
core/extensions/observability/trace.py
core/extensions/registry.py
core/extensions/runtime/__init__.py
core/extensions/runtime/context.py
core/extensions/runtime/executor_bridge.py
core/extensions/runtime/gateway.py
core/extensions/runtime/models.py
core/extensions/runtime/plugin_bridge.py
core/extensions/runtime/skill_invoker.py
core/streaming/README.md
core/streaming/__init__.py
core/streaming/collector.py
core/streaming/dispatcher.py
core/streaming/replay.py
plugin.json
plugin.py
runtime/__init__.py
runtime/wrapper.py
schemas/extension-manifest.schema.json
scripts/__init__.py
scripts/build_extension.py
scripts/deploy_extension.py
scripts/rollback_extension.py
scripts/verify_extension.py
```

### 11.2 WeCom candidate tree (failed in real Runtime)

```text
README.md
adapter/__init__.py
adapter/wecom/__init__.py
adapter/wecom/runtime.py
contracts/__init__.py
contracts/artifact.py
contracts/channel.py
contracts/message.py
contracts/skill.py
contracts/stream_consumer.py
contracts/stream_renderer.py
contracts/streaming.py
core/__init__.py
core/contracts/__init__.py
core/contracts/artifact.py
core/contracts/channel.py
core/contracts/message.py
core/contracts/skill.py
core/contracts/stream_consumer.py
core/contracts/stream_renderer.py
core/contracts/streaming.py
core/extensions/README.md
core/extensions/__init__.py
core/extensions/lifecycle/__init__.py
core/extensions/lifecycle/health.py
core/extensions/lifecycle/manager.py
core/extensions/lifecycle/models.py
core/extensions/loader.py
core/extensions/models.py
core/extensions/observability/__init__.py
core/extensions/observability/health_store.py
core/extensions/observability/metrics.py
core/extensions/observability/models.py
core/extensions/observability/trace.py
core/extensions/registry.py
core/extensions/runtime/__init__.py
core/extensions/runtime/context.py
core/extensions/runtime/executor_bridge.py
core/extensions/runtime/gateway.py
core/extensions/runtime/models.py
core/extensions/runtime/plugin_bridge.py
core/extensions/runtime/skill_invoker.py
core/streaming/README.md
core/streaming/__init__.py
core/streaming/collector.py
core/streaming/dispatcher.py
core/streaming/replay.py
plugin.json
plugin.py
plugins/wecom/manifest.yaml
plugins/wecom/recovered/wecom-node/wecom_bridge.mjs
runtime/__init__.py
runtime/wrapper.py
schemas/extension-manifest.schema.json
scripts/__init__.py
scripts/build_extension.py
scripts/deploy_extension.py
scripts/rollback_extension.py
scripts/verify_extension.py
```

### 11.3 WeChat Customer candidate tree (failed in real Runtime)

```text
README.md
adapter/__init__.py
adapter/wechat_customer/__init__.py
adapter/wechat_customer/runtime.py
contracts/__init__.py
contracts/artifact.py
contracts/channel.py
contracts/message.py
contracts/skill.py
contracts/stream_consumer.py
contracts/stream_renderer.py
contracts/streaming.py
core/__init__.py
core/contracts/__init__.py
core/contracts/artifact.py
core/contracts/channel.py
core/contracts/message.py
core/contracts/skill.py
core/contracts/stream_consumer.py
core/contracts/stream_renderer.py
core/contracts/streaming.py
core/extensions/README.md
core/extensions/__init__.py
core/extensions/lifecycle/__init__.py
core/extensions/lifecycle/health.py
core/extensions/lifecycle/manager.py
core/extensions/lifecycle/models.py
core/extensions/loader.py
core/extensions/models.py
core/extensions/observability/__init__.py
core/extensions/observability/health_store.py
core/extensions/observability/metrics.py
core/extensions/observability/models.py
core/extensions/observability/trace.py
core/extensions/registry.py
core/extensions/runtime/__init__.py
core/extensions/runtime/context.py
core/extensions/runtime/executor_bridge.py
core/extensions/runtime/gateway.py
core/extensions/runtime/models.py
core/extensions/runtime/plugin_bridge.py
core/extensions/runtime/skill_invoker.py
core/streaming/README.md
core/streaming/__init__.py
core/streaming/collector.py
core/streaming/dispatcher.py
core/streaming/replay.py
plugin.json
plugin.py
plugins/wechat-customer/manifest.yaml
plugins/wechat-customer/recovered/wecom_kf_gateway_v345.py
runtime/__init__.py
runtime/wrapper.py
schemas/extension-manifest.schema.json
scripts/__init__.py
scripts/build_extension.py
scripts/deploy_extension.py
scripts/rollback_extension.py
scripts/verify_extension.py
```

## 12. Phase 12.7.1 namespace correction

`build_qwenpaw_plugin()` now derives a private import package from each official
Plugin id, for example:

```text
qwenpaw_plugin_wecom_extension_channel.adapter.wecom.runtime
qwenpaw_plugin_wechat_customer_extension_channel.adapter.wechat_customer.runtime
```

The release entry explicitly loads that package from its own extracted
directory with `importlib` package metadata and does not mutate `sys.path`.
Bundled internal imports are mechanically rewritten into the same private
namespace. The compatibility paths `adapter/wecom/` and
`adapter/wechat_customer/` remain present and directly importable in a clean
ZIP-only environment. No checked-in Adapter, historical Bridge/Gateway, or
Extension Runtime Gateway business source was changed.

Corrected release artifacts:

| Package | SHA256 | Offline status |
| --- | --- | --- |
| `wecom-extension-channel-v0.1.0-recovered.zip` | `cc934244a12dddec2b82094d75ea8323eec051a345aa7c7cafcbdc96c5d235e6` | Isolated entry/import PASS |
| `wechat-customer-extension-channel-v0.1.0-recovered.zip` | `e9d14de62760aa06abfa0110ce5ed358c670d53a70b2e561bf94de6464a4f2e6` | Isolated entry/import PASS |

The already successful Telegram artifact was not regenerated. Its SHA256
remains `fefbc537abd3f79b886564c5567230a8ab36d2d0a01a16dbe7c41a8f27d0fc9d`.
The generic builder will use a private namespace if Telegram is rebuilt in a
future release, but this correction does not alter the validated Telegram ZIP.

Acceptance now covers both failure modes that Phase 12.6 missed:

1. each ZIP is extracted separately, with no repository root in `PYTHONPATH`;
   direct `import adapter.<channel>` and the official `plugin.py` entry pass;
2. Telegram, WeCom, and WeChat Customer entries load sequentially in one
   isolated Python process, and each Adapter resolves from its unique package;
3. no Python file in a generated release contains `sys.path.insert`.

Repository acceptance result: **114/114 tests PASS** using the locked local
development environment (`.venv`). The same-process namespace probe and the
three direct ZIP-only import probes are included in that total.

The corrected WeCom ZIP remains an offline fallback/reference artifact; a real
reinstall is not planned because production uses the built-in 企业微信 Channel.
The WeChat Customer package remains **OFFLINE NAMESPACE FIX VALIDATED / CUSTOM
CAPABILITY TO VERIFY**; package installation is not authorized until the
separate business-chain assessment is complete.
