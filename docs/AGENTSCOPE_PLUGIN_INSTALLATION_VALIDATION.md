# AgentScope/QwenPaw Plugin Installation Validation

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

## 9. Required next validation phase

Without changing historical provider logic, a later implementation phase must:

1. build a self-contained official Plugin archive containing the generic
   wrapper, required `core` modules, existing Adapter, and internal Manifest;
2. remove source-repository path assumptions from the installed entry layout;
3. add a thin tenant-version-compatible QwenPaw `BaseChannel` facade that
   delegates to the existing Adapter;
4. validate `PluginApi.register_channel(...)` without embedding historical
   Bridge/Gateway business logic;
5. install in a disposable QwenPaw v2.1 environment while the Runtime is
   offline;
6. verify Plugin list/info, Channel registration, enable/disable, health,
   uninstall, and rollback;
7. only then perform a secret-injected staging test against supervised external
   processes.

No production or cloud installation should occur before these blockers are
closed.
