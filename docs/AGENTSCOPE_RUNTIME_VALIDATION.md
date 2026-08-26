# AgentScope Runtime Deployment Validation

> Channel policy: Install Plans for historical Telegram/WeCom packages are
> simulation evidence only and are not production plans. Use QwenPaw v2.1.0
> built-in Channels; assess WeChat Customer separately.

## 1. Validation objective

Phase 9.0 validates the deployment handoff up to—but not including—real
AgentScope Runtime discovery:

```text
Local Repository
      |
      v
Release Package
      |
      v
AgentScope Deployment Bridge
      |
      v
AgentScope Workspace mapping and Install Plan
      |
      v
Runtime Discovery
      `-- NOT_EXECUTED in Phase 9.0
```

The phase proves that a local Extension release can be validated, classified,
mapped, checked for secret readiness, represented as an installation plan, and
reported consistently. It does not claim that a real AgentScope/QwenPaw
Runtime has loaded or executed the Extension.

## 2. Boundary

This validation covers:

- immutable release-package SHA256 and ZIP verification;
- Manifest, package identity, declared path, and excluded-file validation;
- Skill, Plugin, and Adapter classification;
- safe logical paths under an AgentScope Workspace root;
- required-secret name checks;
- deterministic Install Plan and Rollback Plan generation;
- deterministic `install-report.json` generation.

It does not:

- connect to AgentScope Cloud or a local AgentScope service;
- upload or extract an Extension package;
- create or modify the target Workspace;
- call Runtime discovery, reload, enable, start, or health APIs;
- inject secret values;
- modify Agent, Gateway, Message Model, AgentScope Runtime, or QwenPaw Runtime;
- validate production provider connectivity.

## 3. Local Repository to Release Package

The source repository remains the development source of truth. Phase 9 uses
packages produced by `scripts/build_extension.py`, not live source directories.

Each package must contain its validated Manifest, README, source payload,
generated config template, and release metadata. Runtime files such as `.env`,
secret stores, databases, logs, caches, tokens, and keys remain excluded.

The Deployment Bridge reuses `verify_package()` rather than introducing a
second package parser. A package that fails checksum, ZIP safety, Manifest, or
release identity validation cannot enter an Install or Rollback Plan.

## 4. Workspace classification

The validated mappings are:

| Classification | Workspace target | Phase 9 interpretation |
| --- | --- | --- |
| Skill | `skills/<extension>` | Candidate Workspace Skill payload |
| Plugin | `extensions/plugins/<extension>` | Candidate Plugin staging payload |
| Adapter | `extensions/adapters/<extension>` | Candidate Adapter staging payload |

Only Skills use the known Workspace Skill location. Plugin and Adapter targets
remain QwenPaw Extension staging areas because this repository does not own the
target Runtime loader. Runtime-private installation paths must not be guessed.

The mapper normalizes each target, rejects parent traversal, and verifies that
the resolved target stays beneath the supplied Workspace root. Mapping is pure:
the target directories are not created.

## 5. Install Plan validation

An Install Plan is ready only when:

1. package verification has completed successfully;
2. Manifest identity maps to one supported Extension type;
3. the Workspace target is safe;
4. every declared required-secret name is available.

The ordered declarative actions are:

1. verify package;
2. check secret requirements;
3. prepare target;
4. install payload;
5. verify Workspace payload.

Plan generation does not execute these actions. Missing secrets produce a valid
reviewable plan with `ready=false`; they never cause the bridge to request or
store secret values.

## 6. Secret validation

Secret checks operate on names only. For example:

```text
required:  WECOM_BOT_ID, WECOM_BOT_SECRET, SN_API_KEY
available: WECOM_BOT_ID
missing:   WECOM_BOT_SECRET, SN_API_KEY
ready:     false
```

Passing a mapping of names to values is rejected. Extra infrastructure secret
names are ignored rather than serialized, so the report does not expose the
complete secret inventory of a deployment environment.

## 7. Rollback Plan

Phase 9 adds a package-based, declaration-only Rollback Plan. Inputs are:

- the current verified Extension package;
- the selected previous verified package;
- the logical Workspace root;
- secret names available for the selected previous version.

Both packages must have the same Extension name and type and different
versions. The previous package maps to the exact same Workspace target. Its
secret requirements—not the current version's requirements—determine rollback
readiness.

Rollback actions are:

1. verify rollback package;
2. check rollback-version secrets;
3. preserve the current target;
4. restore the selected package payload;
5. verify the resulting Workspace payload.

This plan is distinct from `scripts/rollback_extension.py`. That older script
operates on versions already installed in the local lifecycle simulation.
Phase 9 Rollback Plan describes a future AgentScope Workspace handoff and does
not switch pointers, copy files, delete files, or activate Runtime code.

## 8. Install report

`scripts/generate_install_report.py` generates a deterministic JSON report:

```json
{
  "schema_version": "qwenpaw-agentscope-install-report.v1",
  "workspace_root": "<logical absolute workspace path>",
  "runtime_discovery": "NOT_EXECUTED",
  "all_ready": false,
  "extensions": [
    {
      "extension": "wecom",
      "type": "plugin",
      "version": "0.1.0-recovered",
      "target_path": "<workspace>/extensions/plugins/wecom",
      "required_secrets": ["SN_API_KEY", "WECOM_BOT_ID", "WECOM_BOT_SECRET"],
      "missing_secrets": ["SN_API_KEY"],
      "ready": false,
      "plan_id": "plan_<deterministic-id>"
    }
  ]
}
```

The required fields `extension`, `version`, `target_path`,
`required_secrets`, and `ready` are always present. Type, missing-secret names,
and Install Plan identity are included for auditability.

Reports are sorted by Extension name and written atomically. The output path
must use `.json` and remain outside the target Workspace, preventing report
generation from modifying the Workspace under validation.

Example offline command:

```powershell
python scripts/generate_install_report.py `
  --package dist/extensions/pdf-editor-v1.2.0.skill.zip `
  --package dist/extensions/wecom-v0.1.0-recovered.plugin.zip `
  --workspace D:\staging\agentscope-workspace `
  --available-secret WECOM_BOT_ID `
  --output install-report.json
```

This command reads local packages and writes only the report. It does not
connect to or upload anything to AgentScope.

## 9. Runtime Discovery status

`runtime_discovery=NOT_EXECUTED` is mandatory in the Phase 9 report. `ready`
means only “offline prerequisites are satisfied”; it must not be interpreted as
“installed,” “enabled,” “running,” or “discovered by Runtime.”

Real Runtime Discovery validation requires a separately authorized staging
phase with an exact AgentScope/QwenPaw version and an official deployment API.
That phase must record at least:

- deployment/activation receipt;
- Runtime discovery result and loaded version;
- Runtime health result;
- supported unload or rollback result;
- secret provider and environment identity without values.

Until those records exist, deployment status remains offline-plan-only.

## 10. Offline test coverage

`tests/deployment/test_runtime_validation.py` verifies:

- Install Plan generation for real repository packages;
- Skill, Plugin, and Adapter classifications and targets;
- complete and incomplete secret readiness;
- same-Extension/different-version Rollback Plan rules;
- Rollback Plan action ordering and target preservation;
- deterministic install report fields and ordering;
- explicit `NOT_EXECUTED` Runtime discovery status;
- absence of target Workspace creation;
- rejection of report output inside the target Workspace.

No test imports AgentScope Runtime, starts a Gateway, reads a credential, or
uploads a package.
