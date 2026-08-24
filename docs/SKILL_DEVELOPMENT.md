# Skill Development Standard

## 1. Purpose

This standard defines how new and migrated QwenPaw Skills are packaged, validated, tested, and documented. It does not require the 17 imported Skills to be moved or rewritten immediately.

Existing `SKILL.md` Skills remain supported during migration. Adoption happens one Skill at a time behind compatibility tests.

## 2. Canonical layout

For a multi-file Skill:

```text
skills/<skill-name>/
├── skill.yaml
├── schemas/
│   ├── input.schema.json
│   └── output.schema.json
├── executor/
│   ├── __init__.py
│   └── executor.py
├── tests/
│   ├── fixtures/
│   └── test_executor.py
├── README.md
└── SKILL.md                 # compatibility instructions while required
```

For a small, single-file Skill, this compact form is allowed:

```text
skills/pdf/
├── skill.yaml
├── executor.py
├── schemas/
├── tests/
├── README.md
└── SKILL.md
```

`schemas/` is the canonical directory name. Older notes may call it `schema/`; new Skills must not create both directories. `executor/` is preferred when execution needs more than one module.

## 3. Required files

### `skill.yaml`

Machine-readable Skill metadata and execution declaration.

Required fields:

```yaml
schema_version: 1
name: pdf
version: 1.0.0
description: Read, create, inspect, and transform PDF files.
entrypoint: executor.executor:execute
input_schema: schemas/input.schema.json
output_schema: schemas/output.schema.json
capabilities:
  - document.pdf.read
  - document.pdf.write
permissions:
  filesystem: workspace
  network: false
timeouts:
  execution_seconds: 120
artifacts:
  enabled: true
```

Rules:

- `name` is lowercase and stable after release.
- `version` follows semantic versioning.
- `entrypoint` resolves to one callable execution boundary.
- Capabilities describe outcomes, not implementation libraries.
- Permissions use least privilege and must never contain credentials.
- Schema paths are relative to the Skill root.

### `schemas/`

Contains versioned JSON Schema documents for inputs, outputs, errors, and artifacts when needed.

Requirements:

- Reject unknown fields unless forward compatibility explicitly requires them.
- Define size, range, and enum constraints.
- Use stable machine-readable error codes.
- Avoid channel-specific fields.
- Reference file artifacts by platform artifact descriptors, not arbitrary public URLs.

### `executor/` or `executor.py`

Contains execution code only. It must not perform channel delivery, read global credentials directly, or mutate Agent configuration.

An executor receives validated input and an execution context containing trace, cancellation, workspace, credential references, and event emission interfaces. It returns a schema-valid result or raises a normalized Skill error.

### `tests/`

Minimum test categories:

1. Manifest and schema validation.
2. Happy-path execution.
3. Invalid input and boundary values.
4. Permission and path-safety behavior.
5. Cancellation and timeout behavior where applicable.
6. Artifact existence and integrity.
7. Regression fixtures for migrated behavior.

Document and media Skills must also validate rendered or semantic output appropriate to the format. A file merely existing is not sufficient proof of correctness.

### `README.md`

Human-facing documentation covering:

- purpose and supported operations;
- inputs, outputs, and artifacts;
- runtime dependencies;
- configuration and credential references;
- examples;
- limitations;
- test command;
- compatibility and migration notes.

### `SKILL.md`

Agent-facing activation and operating instructions. During gradual migration it remains the compatibility entry used by QwenPaw. It must agree with `skill.yaml` and `README.md`; contradictory capability claims are release blockers.

## 4. Execution contract

A future common executor contract should support:

- validated structured input;
- `trace_id` and `tool_call_id`;
- scoped workspace access;
- cancellation and deadlines;
- credential references resolved outside the manifest;
- progress and artifact events;
- structured results and errors.

This is a target contract only. Existing executors are not changed as part of the architecture baseline.

## 5. Error contract

Skill errors must expose:

| Field | Meaning |
| --- | --- |
| `code` | Stable programmatic error code |
| `message` | Safe user-facing summary |
| `retryable` | Whether retry may succeed without changing input |
| `details` | Redacted structured diagnostics |
| `trace_id` | Correlation identifier |

Executors must not return stack traces, tokens, credentials, or private source documents to channels by default.

## 6. Versioning and compatibility

- Patch: behavior-preserving fixes.
- Minor: backward-compatible operations or fields.
- Major: incompatible schema or behavior changes.
- Input schemas may accept older compatible payloads during a documented deprecation window.
- Existing Skill directories are migrated independently; bulk rewrites are prohibited.

## 7. Migration checklist

- Inventory current operations and dependencies.
- Capture representative regression fixtures.
- Add metadata and schemas without changing execution behavior.
- Wrap the existing entrypoint rather than rewriting it.
- Run old-path and new-path parity tests.
- Document limits and security requirements.
- Switch one caller behind a reversible compatibility flag.
- Remove the compatibility path only after an agreed release window.

PDF Editor is not the first migration candidate because it is production-sensitive. Start with a small, low-risk Skill such as `file_reader` after the platform contracts exist.
