# AgentScope Deployment Bridge

> Channel policy: this offline mapper does not authorize replacement Channels.
> Telegram、企业微信和微信 use QwenPaw v2.1.0 built-ins; repository
> Telegram/WeCom packages are reference-only. WeChat Customer is `TO VERIFY`.

## 1. Purpose

Phase 8.5 defines an offline bridge from a verified QwenPaw Extension release
package to a declarative AgentScope Workspace Install Plan.

```text
local Git repository
        |
        v
Extension Release Package (.zip + SHA256)
        |
        v
AgentScopeDeploymentAdapter
        |-- package integrity and Manifest validation
        |-- WorkspaceMapper
        |-- required-secret name check
        `-- deterministic InstallPlan
                |
                v
future approved AgentScope Workspace installer
```

This phase produces data only. It does not extract a package, create a
Workspace directory, inject configuration, start an Extension, or connect to a
real AgentScope/QwenPaw environment.

## 2. Boundary

The Deployment Bridge owns:

- parsing an existing Extension ZIP;
- reusing package checksum, ZIP safety, release metadata, Manifest, declared
  path, generated config template, and secret-exclusion verification;
- assigning a safe logical target beneath a supplied Workspace root;
- comparing required secret names with available secret names;
- generating a stable, serializable Install Plan.

It does not own:

- AgentScope or QwenPaw Runtime installation APIs;
- Agent configuration, prompts, memory, sessions, or Runtime state;
- Plugin/Adapter process supervision or Channel traffic;
- Gateway databases, cursors, migrations, credentials, or business logic;
- secret values or production configuration rendering;
- filesystem activation, rollback, or production release approval.

No AgentScope Runtime module is imported by `core/deployment/`.

## 3. Package parsing and Manifest validation

`AgentScopeDeploymentAdapter.parse_package()` delegates first to the existing
`scripts.verify_extension.verify_package()` implementation. A package must
therefore pass all current Extension release checks before it can be mapped:

- SHA256 sidecar or explicitly supplied digest;
- ZIP integrity, entry-count and uncompressed-size limits;
- safe relative ZIP paths;
- required `manifest.yaml`, `README.md`, release metadata, and generated config
  template;
- Manifest schema and Extension type validation;
- declared executor, entrypoint, schema, test, and config paths;
- release/Manifest identity and file-count consistency;
- secret, database, log, cache, key, token, and environment-file exclusions.

The bridge then creates `ExtensionPackageDescriptor`, containing only package
identity, checksum, file names, and declared required-secret names. It never
imports an executor or entrypoint.

## 4. Workspace mapping

`WorkspaceMapper` uses the following conservative targets:

| Extension type | Relative Workspace target | Meaning |
| --- | --- | --- |
| Skill | `skills/<name>` | AgentScope Workspace Skill payload |
| Plugin | `extensions/plugins/<name>` | QwenPaw Extension staging area |
| Adapter | `extensions/adapters/<name>` | QwenPaw Extension staging area |

Skills map to the existing Workspace Skill convention. Plugin and Adapter
packages do not map directly into an assumed Runtime-private directory because
the current repository does not contain, control, or version the AgentScope
Runtime loader. A later installer must use the official interface supported by
the exact target Runtime version before activating staged content.

All targets are normalized relative paths. Absolute paths, parent traversal,
and paths escaping the supplied Workspace root are rejected. Mapping does not
call `mkdir`, extract files, or inspect an existing Workspace.

## 5. Secret requirement check

Runtime Plugin/Adapter Manifests declare `required_secrets`. Skills currently
have no secret field in the standardized Skill Manifest, so their requirement
set is empty.

The bridge accepts only names of secrets known to be available:

```python
plan = adapter.create_install_plan(
    archive,
    workspace_root,
    available_secrets=("WECOM_BOT_ID", "WECOM_BOT_SECRET"),
)
```

A mapping such as `{"TOKEN": "value"}` is rejected. Secret values must never
enter the bridge, Install Plan, logs, tests, or Git. The result records:

- `required`: names declared by the Manifest;
- `available`: declared names present in the supplied name set;
- `missing`: required names not present;
- `satisfied`: whether `missing` is empty.

Extra infrastructure secret names are ignored and are not serialized, avoiding
disclosure of the deployment environment's complete secret inventory.

## 6. Install Plan

An `InstallPlan` uses schema `qwenpaw-agentscope-install-plan.v1` and contains:

- deterministic `plan_id` derived from package SHA256 and target mapping;
- verified `ExtensionPackageDescriptor`;
- `WorkspaceMapping`;
- `SecretRequirementCheck`;
- ordered declarative steps;
- computed `ready` status.

The first version emits five steps:

1. `verify_package` — verify the immutable source release;
2. `check_secrets` — confirm all required names are available;
3. `prepare_target` — prepare the mapped target under an approved installer;
4. `install_payload` — stage/install package content under that installer;
5. `verify_workspace` — verify installed files and identity.

These steps are instructions, not callbacks. Creating a plan cannot execute any
step. A plan with missing secrets remains serializable for review but has
`ready=false` and must not be installed.

## 7. Example mapping

```text
pdf-editor-v1.2.0.skill.zip
        -> workspace/skills/pdf-editor

wecom-v0.1.0-recovered.plugin.zip
        -> workspace/extensions/plugins/wecom

telegram-v0.1.0-recovered.adapter.zip
        -> workspace/extensions/adapters/telegram
```

Package contents remain rooted at `manifest.yaml` inside the ZIP. The future
installer is responsible for safe staging and atomic activation at the mapped
target.

## 8. Local simulation guarantees

`tests/deployment/test_agentscope_bridge.py` builds real repository Skill,
Plugin, and Adapter packages in a temporary directory and verifies:

- package and Manifest parsing;
- rejection of a package with altered Manifest content;
- all three Workspace target mappings;
- deterministic step ordering and plan ID;
- no Workspace filesystem creation;
- incomplete and complete secret requirements;
- rejection of secret value mappings.

Tests do not contact AgentScope, QwenPaw, provider APIs, or a secret manager.

## 9. Future activation phase

Before a plan can become a real deployment, a separately reviewed phase must:

1. verify the exact AgentScope/QwenPaw Runtime version and supported deployment
   API;
2. back up the target Workspace using official capabilities;
3. implement staging, atomic target replacement, installed-file records, and
   rollback without touching Agent or Runtime core;
4. obtain secret values from an approved provider at execution time;
5. activate Plugin/Adapter packages only through a supported Runtime Extension
   mechanism;
6. run health checks and preserve the previous immutable release.

If the target Runtime does not support Plugin or Adapter activation, the plan
must stop at staging. Copying files into guessed Runtime directories is not an
approved workaround.
