# AgentScope Deployment Capability Report

## 1. Purpose and scope

This report records the deployment surfaces confirmed for the current AgentScope/QwenPaw tenant during Phase 11.0. It is a read-only capability probe: no package was uploaded, no URL was submitted, no secret was read, and no Runtime, Plugin, Channel, or Gateway process was started or modified.

> **Strategic update (2026-08-26):** the QwenPaw v2.1.0 Console confirms that
> Telegram, 企业微信, and 微信 are built-in Channels. Production must use those
> built-in entries. The custom Channel Plugin path below applies only to a
> capability that QwenPaw does not provide, currently `WeChat Customer / TO
> VERIFY`; it is not a roadmap for custom Telegram or WeCom `BaseChannel`
> development. See `QWENPAW_CHANNEL_STRATEGY.md`.

Probe date: 2026-08-25 (Asia/Shanghai).

Evidence levels used below:

- `TENANT_VERIFIED`: visible in the current tenant UI or already exercised successfully in this tenant.
- `OFFICIAL_DOCUMENTED`: supported by current official QwenPaw documentation, but not exercised in this probe.
- `NOT_CONFIRMED`: no dedicated tenant or official package entry was found.
- `FORMAT_ADAPTATION_REQUIRED`: an official deployment surface exists, but this repository's package is not yet in that surface's native format.

## 2. Observed tenant environment

User-provided tenant screenshots confirm:

- QwenPaw version: **v2.1.0**.
- Workspace navigation includes Skills, Tools, MCP, ACP, Channels, Backup, and Plugin Management.
- Plugin Management contains Installed, Official Plugins, and Plugin Marketplace views.
- Plugin Management exposes **Publish Plugin** and **Install Plugin** actions.
- Install Plugin accepts a local folder or ZIP file and also accepts a Plugin ZIP URL.
- The install dialog warns that some hook or monkey-patch Plugins may require an application restart.

The screenshots contain no tenant identifier or credentials and are not copied into the repository.

## 3. Capability matrix

| Repository artifact | Current tenant entry | Capability status | Direct compatibility | Conclusion |
| --- | --- | --- | --- | --- |
| `skills/*.skill.zip` | Skill Center / Skill Pool upload and activation | `TENANT_VERIFIED` | Verified for PDF Editor v1.2.0 | Supported |
| `plugins/*.plugin.zip` | Settings → Plugin Management → Install Plugin → folder/ZIP or URL | `TENANT_VERIFIED` for official Plugin ZIP | `FORMAT_ADAPTATION_REQUIRED` for current repository packages | Entry exists, package contract must be adapted |
| `adapters/*.adapter.zip` | No standalone Adapter upload page found | `NOT_CONFIRMED` | Current package has no official standalone target | Not directly supported |
| Channel Plugin ZIP | Plugin Management → Install Plugin, then Control → Channels | `TENANT_VERIFIED` entry and `OFFICIAL_DOCUMENTED` channel type | Requires official QwenPaw Channel Plugin contract | Custom-only path; not used for built-in Telegram/WeCom/WeChat |

## 4. Skill upload capability

### Current tenant result

Status: **SUPPORTED / TENANT_VERIFIED**.

`pdf-editor-v1.2.0.skill.zip` was previously uploaded through the AgentScope Skill Center, activated in the Workspace, invoked by an Agent, and returned an Artifact successfully. That real execution is recorded in `AGENTSCOPE_PDF_EDITOR_VALIDATION.md`.

This proves the current tenant can accept at least the validated PDF Editor Skill package. It does not prove every arbitrary ZIP or every future Skill Manifest is compatible.

### Upload entry

```text
AgentScope/QwenPaw tenant
  → Skill Center / Skill Pool
  → Upload or import Skill package
  → Activate in target Workspace/Agent
```

Official QwenPaw CLI also documents Skill install, enable, disable, info, and test operations for a Workspace or shared Pool: [QwenPaw CLI — Skills](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/cli.en.md#skills).

### Supported package expectation

The validated package contains the Skill definition and execution assets required by the tenant. Before uploading another Skill, verify:

- the archive has one unambiguous Skill root;
- Skill metadata and entry files match the target tenant version;
- the archive contains no `.env`, token, credential, log, cache, or runtime database;
- the expected executor and schema files exist;
- package SHA-256 is recorded before upload.

## 5. Plugin deployment capability

### Current tenant result

Status: **OFFICIAL PLUGIN INSTALL ENTRY SUPPORTED / TENANT_VERIFIED**.

The QwenPaw v2.1.0 tenant exposes:

```text
Settings
  → Plugin Management
  → Install Plugin
  → local folder or ZIP
     OR Plugin ZIP URL
```

The tenant also exposes Publish Plugin, Official Plugins, and Plugin Marketplace surfaces. No package was selected or installed during this probe.

### Official Plugin package contract

Official QwenPaw documentation requires a backend Plugin to contain at least:

```text
my-plugin/
├── plugin.json
├── plugin.py
└── README.md
```

`plugin.json` declares the Plugin ID, version, type, backend entry, dependencies, and compatible QwenPaw version. Official CLI installation supports a local directory or ZIP URL and documents that CLI Plugin operations require QwenPaw to be offline: [QwenPaw Plugin Management](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md#plugin-management), [Plugin package structure](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md#backend-plugins).

### Compatibility with this repository

At the time of the Phase 11 probe, the repository's original Extension packages
contained only the internal `manifest.yaml`. Later Phase 12 historical facades
added top-level `plugin.json` and `plugin.py` candidates for packaging research.
Those later candidates do not change the production Channel strategy: Telegram
and WeCom candidates are `LEGACY / FALLBACK / REFERENCE ONLY`; WeChat Customer
remains `CUSTOM / TO VERIFY`.

Therefore:

- the tenant accepts Plugin ZIP files in general;
- the `.plugin.zip` filename suffix is not sufficient for compatibility;
- current repository `.plugin.zip` artifacts must **not** be uploaded unchanged;
- each Plugin needs an official QwenPaw packaging facade before tenant installation can be tested.

Status for current repository packages: **FORMAT_ADAPTATION_REQUIRED**.

## 6. Adapter and Channel deployment capability

### Standalone Adapter package

Status: **NO DEDICATED ENTRY CONFIRMED**.

No tenant page or official documentation was found for installing a standalone `*.adapter.zip` artifact as an independent Runtime type. The tenant's Channels page manages available Channel instances and configuration; it is not evidence of a generic Adapter package loader.

The repository's `adapters/telegram/*.adapter.zip` is an internal Extension release artifact and should not be uploaded directly to Skill Center or Plugin Management.

### Official Channel extension path

QwenPaw officially models custom Channels as Plugins. A Channel Plugin uses:

- `plugin.json` with `type: "channel"`;
- a backend `plugin.py` entry;
- a `BaseChannel` implementation;
- `api.register_channel(...)` registration;
- optional HTTP router registration for webhooks.

After installation, the Channel appears under Control → Channels for configuration and enable/disable operations. See the official [Custom Channel Plugin example](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md#example-10-register-a-custom-channel) and [QwenPaw channel contribution contract](https://github.com/agentscope-ai/QwenPaw/blob/main/CONTRIBUTING.md#adding-new-channels).

Custom-only mapping, after proving that no built-in Channel covers the required
business semantics:

```text
verified custom Adapter + separately supervised Gateway
  → official QwenPaw Channel Plugin facade
  → plugin.json(type=channel)
  → Plugin Management ZIP install
  → Control → Channels configuration
```

This path must not be used to duplicate Telegram, WeCom, or WeChat built-in
capabilities. For the current repository it is relevant only to the separate
WeChat Customer `open_kfid`/`external_userid`/cursor/Gateway chain, and only
after capability verification.

## 7. Supported and unsupported types

### Supported now

- Skill package upload and activation: confirmed by PDF Editor real Workspace validation.
- Official QwenPaw Plugin folder/ZIP installation: confirmed by current v2.1.0 tenant UI.
- Plugin installation from URL: confirmed by current tenant UI and official documentation.
- Channel Plugin registration: officially supported through the QwenPaw Plugin system.

### Not directly supported or not confirmed

- Direct installation of this repository's `manifest.yaml`-only `.plugin.zip` packages.
- Standalone `.adapter.zip` upload and activation.
- Direct deployment of the repository's Extension Runtime Gateway into managed AgentScope Runtime.
- Direct activation of historical Gateway/Bridge source without an official Plugin facade.
- Treating a logical `workspace/extensions/plugins` or `workspace/extensions/adapters` mapping as a Runtime loader contract.

## 8. Manual deployment options

Manual deployment here means an operator-controlled installation path, not copying files into undocumented tenant directories.

### Skill

1. Build and verify the Skill archive locally.
2. Record SHA-256 and run offline regression tests.
3. Upload through Skill Center/Skill Pool.
4. Activate only in a staging Agent/Workspace.
5. Run invocation and Artifact acceptance tests.
6. Roll back by disabling the new Skill and reactivating the previous version.

### Plugin

1. Add an official `plugin.json` facade outside recovered source.
2. Add a minimal `plugin.py` that registers through `PluginApi` without modifying historical code.
3. Declare `qwenpaw_version` compatibility for the verified tenant version.
4. Package one official Plugin root as ZIP.
5. Run a local QwenPaw v2.1.0 compatibility test while offline.
6. Install through tenant Plugin Management in staging.
7. Restart only if the Plugin type requires it and the operator has an approved maintenance window.

### Adapter / Channel

1. Configure Telegram, 企业微信, and 微信 through their QwenPaw v2.1.0 built-in
   Channel entries.
2. Inject credentials only through the built-in Runtime configuration surface.
3. Validate built-in streaming, media, typing/context, access control, health,
   enable/disable, and rollback behavior in staging.
4. Keep recovered Telegram/WeCom Adapters, Plugins, and Bridges as
   `LEGACY / FALLBACK / REFERENCE ONLY`.
5. For WeChat Customer, first verify whether the Runtime supports
   `open_kfid`, `external_userid`, cursor, Gateway-owned DB, and deduplication.
6. Consider a custom Channel Plugin only if that verification proves a real
   built-in gap and a separate architecture decision authorizes development.

For self-managed QwenPaw only, the official CLI can install local/URL Plugins. Filesystem copying into internal directories should be reserved for documented recovery procedures and must not be used as the managed-tenant default.

## 9. Recommended next integration plan

1. **Accept the built-in Channel strategy** for Telegram, 企业微信, and 微信.
2. **Use Cloud staging** to validate the built-in configuration and lifecycle,
   without installing repository replacement Plugins.
3. **Keep Telegram and WeCom recovery assets unchanged** as fallback/reference
   evidence; packaging PASS does not make them production candidates.
4. **Verify WeChat Customer independently**, including `open_kfid`,
   `external_userid`, cursor, database ownership, deduplication, and rollback.
5. **Keep Hermes at `TO VERIFY`** until its independent role and dependency
   completeness are proven.
6. **Continue PDF Editor through the custom Skill path**, which has real
   Workspace validation.
7. **Record tenant evidence** for every staging decision without storing secret
   values in Git.

## 10. Final conclusion

| Type | Current tenant conclusion |
| --- | --- |
| Skill | Direct upload supported and already validated |
| Official QwenPaw Plugin | Folder/ZIP/URL install entry confirmed in v2.1.0 tenant |
| Current repository Plugin package | Requires official package facade before upload |
| Standalone Adapter package | No dedicated deployment entry confirmed |
| Built-in Telegram/WeCom/WeChat | Configure the QwenPaw v2.1.0 built-in Channel; do not deploy replacement Plugins |
| WeChat Customer | `CUSTOM / TO VERIFY`; custom Plugin path only after a proven built-in gap |

The tenant supports more than Skill upload: it has a real Plugin management surface. The remaining boundary is package-contract compatibility, not the absence of a Plugin entry. No evidence currently supports direct activation of the repository's standalone Adapter format.
