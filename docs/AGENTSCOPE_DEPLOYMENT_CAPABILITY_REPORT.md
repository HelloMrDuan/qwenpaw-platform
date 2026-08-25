# AgentScope Deployment Capability Report

## 1. Purpose and scope

This report records the deployment surfaces confirmed for the current AgentScope/QwenPaw tenant during Phase 11.0. It is a read-only capability probe: no package was uploaded, no URL was submitted, no secret was read, and no Runtime, Plugin, Channel, or Gateway process was started or modified.

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
| Channel Plugin ZIP | Plugin Management → Install Plugin, then Control → Channels | `TENANT_VERIFIED` entry and `OFFICIAL_DOCUMENTED` channel type | Requires official QwenPaw Channel Plugin contract | Recommended Adapter/Channel deployment path |

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

The current `qwenpaw-platform` release packages contain the repository's Extension Contract `manifest.yaml`. Historical packages such as WeCom, WeChat Customer, WeChat MP, and Hermes do **not** currently provide a top-level official `plugin.json` plus QwenPaw `plugin.py` registration entry.

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

Recommended mapping:

```text
qwenpaw-platform Adapter + historical Bridge
  → official QwenPaw Channel Plugin facade
  → plugin.json(type=channel)
  → Plugin Management ZIP install
  → Control → Channels configuration
```

This is a future packaging and integration task. It is not implemented by this report.

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

1. Keep MessageEvent/DeliveryReceipt adapters as internal testable components.
2. Wrap the transport in an official Channel Plugin facade.
3. Implement the QwenPaw `BaseChannel` and `PluginApi.register_channel` boundaries without copying historical business logic.
4. Install the resulting official Channel Plugin ZIP through Plugin Management.
5. Inject secrets through tenant configuration only after a separate security review.
6. Enable one staging Channel instance and run provider-level acceptance tests.

For self-managed QwenPaw only, the official CLI can install local/URL Plugins. Filesystem copying into internal directories should be reserved for documented recovery procedures and must not be used as the managed-tenant default.

## 9. Recommended next integration plan

1. **Create an official package conformance checker** for `plugin.json`, backend entry, supported type, dependencies, ZIP root, and QwenPaw version range.
2. **Package one low-risk Plugin pilot** for v2.1.0 without secrets or external connections.
3. **Do not use Hermes as the first pilot** because its recovered dependency snapshot is incomplete and its source tree is large.
4. **Convert Telegram or WeCom to an official Channel Plugin facade** only after the generic Plugin pilot installs and rolls back successfully.
5. **Use Cloud staging** for install, restart, enable, health, message, and uninstall validation.
6. **Record tenant evidence**: masked tenant/workspace ID, QwenPaw build, Plugin ID/version, package SHA-256, install result, restart requirement, health result, and rollback result.
7. **Keep the existing Extension package format** as the repository's internal release and deployment-plan format; produce a separate official QwenPaw deployment artifact rather than silently changing historical packages.

## 10. Final conclusion

| Type | Current tenant conclusion |
| --- | --- |
| Skill | Direct upload supported and already validated |
| Official QwenPaw Plugin | Folder/ZIP/URL install entry confirmed in v2.1.0 tenant |
| Current repository Plugin package | Requires official package facade before upload |
| Standalone Adapter package | No dedicated deployment entry confirmed |
| Channel Adapter | Deploy as an official QwenPaw Channel Plugin, not as `.adapter.zip` |

The tenant supports more than Skill upload: it has a real Plugin management surface. The remaining boundary is package-contract compatibility, not the absence of a Plugin entry. No evidence currently supports direct activation of the repository's standalone Adapter format.
