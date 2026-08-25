# QwenPaw Plugin Self-contained Packaging Model

## 1. Goal and boundary

Phase 12.6 converts the three source-level Channel Plugin facades into
self-contained QwenPaw Plugin ZIPs. After extraction, `plugin.py` and the
internal Extension Manifest can load without adding the `qwenpaw-platform`
repository root to `sys.path`.

This phase changes only Plugin entry bootstrapping and release assembly. It does
not modify or execute:

- Telegram historical Bridge;
- WeCom `wecom_bridge.mjs` or `bot.mjs`;
- WeChat Customer Gateway, database, session, or cursor logic;
- any existing Adapter business behavior;
- Extension Runtime Gateway core behavior.

## 2. Development repository to release package

```text
Development repository
├── plugins/<channel>-channel-plugin/
│   ├── plugin.json
│   ├── plugin.py
│   └── README.md
├── plugins/runtime-wrapper/runtime.py
├── adapters/<channel>/runtime.py
├── core/contracts/
├── core/extensions/
├── core/streaming/
├── schemas/extension-manifest.schema.json
└── internal Extension manifest
             |
             | scripts/build_extension.py
             v
Self-contained official Plugin ZIP
├── plugin.json
├── plugin.py
├── README.md
├── runtime/
│   ├── __init__.py
│   └── wrapper.py
├── adapter/
│   ├── __init__.py
│   └── <channel>/
│       ├── __init__.py
│       └── runtime.py
├── contracts/
├── core/
│   ├── contracts/
│   ├── extensions/
│   └── streaming/
├── schemas/
├── scripts/
└── adapters/ or plugins/
    └── <internal-extension>/
        ├── manifest.yaml
        └── declared entrypoint
```

The top-level `contracts/` directory is the explicit Plugin contract payload.
The mirrored `core/contracts/` path preserves the existing imports used by the
unchanged Adapter and Runtime code. This deliberate duplication avoids a
mechanical rewrite of business modules.

## 3. Dependency collection rules

`build_qwenpaw_plugin()` validates `plugin.json`, resolves its
`meta.extension` mapping, and collects a deterministic dependency closure.

| Release path | Source | Purpose |
| --- | --- | --- |
| `plugin.json` | Channel Plugin facade | Official QwenPaw Manifest |
| `plugin.py` | Channel Plugin facade | Official backend entry |
| `runtime/wrapper.py` | `plugins/runtime-wrapper/runtime.py` | Generic Extension facade |
| `adapter/<channel>/runtime.py` | Existing Adapter | Message and response conversion |
| `contracts/` | `core/contracts/` | Explicit contract payload |
| `core/contracts/` | Existing core | Preserve Adapter imports |
| `core/extensions/` | Existing core | Registry, Lifecycle, Gateway, Health |
| `core/streaming/` | Existing core | Gateway streaming dependency |
| `schemas/` | Repository schema | Internal Manifest validation |
| selected `scripts/` | Existing deployment modules | Lifecycle import closure |
| internal Manifest path | Adapter/Plugin Manifest | Registry discovery |
| declared entrypoint | Historical source file | Manifest path integrity only |

The historical declared entrypoint is copied byte-for-byte only because the
internal Manifest validator requires its path to exist. Packaging and import
tests do not execute it.

## 4. Plugin entry behavior

Each `plugin.py` detects whether `runtime/wrapper.py` and its packaged Adapter
exist beside the official entry.

### Packaged mode

```text
plugin.py
  -> from adapter.<channel>.runtime import ...
  -> from runtime.wrapper import OfficialPluginRuntimeWrapper
  -> repository root = extracted Plugin root
```

The packaged entry does not use `from adapters.xxx`. It adds only its extracted
Plugin root to the import path.

### Source development mode

Repository tests still load the same `plugin.py` before a ZIP exists. In that
mode the entry dynamically resolves existing source modules for development
compatibility. This fallback is not selected after extraction because the
packaged `adapter/` and `runtime/` paths are present.

## 5. Manifest model

Two Manifests serve different layers:

- `plugin.json` is the official QwenPaw Plugin Manifest at the ZIP root.
- `manifest.yaml` is the internal Extension Manifest discovered by
  `ExtensionRegistry` inside the extracted Plugin root.

The builder requires the following values to agree before packaging:

- extension name;
- extension type;
- version;
- runtime;
- declared entrypoint;
- required secret names.

Configuration values must remain empty. Permission declarations must be
non-empty and duplicate-free.

During assembly, the release copy of `plugin.json` rewrites
`meta.extension.adapter_entrypoint` to the packaged `adapter/<channel>/runtime.py`
path and preserves the development repository value as
`meta.extension.source_adapter_entrypoint`. The checked-in source Manifest is
not changed.

## 6. Build command

```powershell
.\.venv\Scripts\python.exe scripts\build_extension.py `
  --output dist\extensions `
  --qwenpaw-plugin telegram-channel-plugin `
  --qwenpaw-plugin wecom-channel-plugin `
  --qwenpaw-plugin wechat-customer-channel-plugin
```

Generated files:

```text
dist/extensions/qwenpaw-plugins/
├── telegram-extension-channel-v0.1.0-recovered.zip
├── wecom-extension-channel-v0.1.0-recovered.zip
├── wechat-customer-extension-channel-v0.1.0-recovered.zip
├── *.zip.sha256
└── SHA256SUMS.txt
```

The output remains Git-ignored. Release Storage or a reviewed GitHub Release
must be used for distribution.

## 7. Phase 12.6 release hashes

| Package | SHA256 |
| --- | --- |
| `telegram-extension-channel-v0.1.0-recovered.zip` | `fefbc537abd3f79b886564c5567230a8ab36d2d0a01a16dbe7c41a8f27d0fc9d` |
| `wecom-extension-channel-v0.1.0-recovered.zip` | `f8aff6b98768c4692e4786ec65b4fc8f0d9e3c745acdc738693ab2b19fd2df57` |
| `wechat-customer-extension-channel-v0.1.0-recovered.zip` | `b57a468cad1b54d4fe2e5f5433e1bdfab7c92f28a0c1c2617741c5b0eb560cfd` |

The builder uses a fixed ZIP timestamp and stable path order. Rebuilding the
same source produces the same hash.

## 8. Self-contained acceptance

Each package is extracted to a new empty directory and loaded with Python
isolated mode (`-I`). The validation requires:

- official root files exist;
- packaged Adapter and Runtime wrapper exist;
- repository root is not injected into `sys.path`;
- `plugin.py` imports successfully;
- `SELF_CONTAINED=true`;
- Adapter module resolves from `adapter.<channel>`;
- wrapper resolves from `runtime.wrapper`;
- internal Manifest loads through `ExtensionRegistry`;
- version and Extension identity match;
- cache, database, log, token, and credential files are absent;
- a second build produces the same SHA256.

Phase 12.6 result:

| Plugin | Isolated import | Manifest load | Repository-root dependency |
| --- | --- | --- | --- |
| Telegram | PASS | PASS | NONE |
| WeCom | PASS | PASS | NONE |
| WeChat Customer | PASS | PASS | NONE |

Overall: **PLUGIN SELF-CONTAINED PACKAGING PASS**.

Automated verification at acceptance:

- self-contained packaging tests: `4/4 PASS`;
- complete repository regression: `112/112 PASS`;
- final ZIP isolated imports: `3/3 PASS`;
- forbidden runtime/secret file-name scan: `0` findings.

## 9. Remaining Runtime boundary

Self-contained Python import does not equal a completed QwenPaw Channel
installation. The Plugins still register only their safe metadata startup hook;
a target-version-compatible QwenPaw `BaseChannel` facade and
`PluginApi.register_channel(...)` validation remain a later phase.

No real AgentScope/QwenPaw installation, secret injection, provider API call,
Bridge startup, or Gateway startup is performed here.
