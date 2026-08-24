# QwenPaw Workspace Incremental Migration Plan

## 1. Objective

Transform the imported QwenPaw / AgentScope runtime workspace into a long-lived engineering project without losing existing capabilities, moving all code at once, or rewriting AgentScope core.

## 2. Non-negotiable constraints

- Preserve all existing `skills/` content.
- Preserve `configs/agent.json` and the current configuration structure.
- Preserve `memory/`, `sessions/`, `mem_agent/`, `mem_metadata/`, `mem_session/`, and `checkpoints/` locally.
- Keep sensitive and runtime data outside Git.
- Do not modify PDF Editor until a dedicated, regression-tested migration unit is approved.
- Do not mix directory migration with behavior changes.
- Every cutover must have a rollback path.

## 3. Current structure

```text
qwenpaw-platform/
├── configs/             # exported agent, channel, Skill, and MCP configuration
├── skills/              # 17 imported Skills
├── scripts/             # exported operational scripts
├── drivers/             # Tavily MCP driver
├── digest/              # operational knowledge and runbooks
├── memory/              # local runtime memory
├── sessions/            # local session state
├── mem_agent/
├── mem_metadata/
├── mem_session/
├── checkpoints/
├── README.md
└── MIGRATION.md
```

The export documentation described channel and core directories, but the actual archive did not include channel implementation source or AgentScope core source.

## 4. Target structure

```text
qwenpaw-platform/
├── apps/                # runnable compositions and deployment entrypoints
├── core/                # platform contracts and adapters around AgentScope
├── channels/            # channel transport adapters
├── skills/              # preserved existing Skills plus gradual standardization
├── configs/             # versioned non-secret configuration and local examples
├── docs/                # architecture and engineering standards
├── tests/               # platform contract and integration tests
├── scripts/             # operational and migration scripts
├── drivers/             # MCP and external tool driver definitions
├── digest/              # retained operational knowledge
├── memory/              # preserved local runtime structure
├── sessions/            # preserved local runtime structure
├── mem_agent/
├── mem_metadata/
├── mem_session/
└── checkpoints/
```

The target structure is additive. Existing directories stay in place until a specific migration unit proves parity.

## 5. Directory mapping

| Current source | Target owner | Migration method |
| --- | --- | --- |
| `configs/agent.json` | `configs/` | Keep in place; later add validated local overlays without changing current file |
| `configs/skill.json` | `configs/` | Keep in place; introduce generated registry only after compatibility tests |
| `skills/*` | `skills/*` | Keep paths stable; add manifests and tests one Skill at a time |
| `scripts/*` | `scripts/` or future `apps/<app>/ops/` | Keep in place until the owning application exists and runbook is verified |
| `drivers/mcp/*` | `drivers/mcp/*` | Keep in place; future Tool Router consumes through an adapter |
| channel config blocks | `channels/<channel>/` | Create adapters without moving or deleting current config blocks |
| AgentScope runtime behavior | `core/agentscope_adapter/` | Wrap public/runtime interfaces; never copy or rewrite AgentScope internals |
| message payload handling | `core/messages/` | Introduce versioned normalized schema in Phase 2 |
| response/progress handling | `core/streaming/` | Introduce event contract in Phase 3 |
| `memory/`, `sessions/`, `mem_*`, `checkpoints/` | Existing local paths | Preserve structure and ignore data; add storage abstraction only after replay tests |
| cross-component validation | `tests/` | Add fixtures and contract tests before each cutover |

## 6. Migration sequence

### Step 0: Architecture baseline

Add documentation, directory skeletons, migration constraints, and secret scanning. No business code moves.

Acceptance:

- Existing tracked business files are unchanged.
- Target directories exist.
- Sensitive runtime content is not tracked.

### Step 1: Reproducible local inventory

Record Python, Node.js, QwenPaw, AgentScope, MCP, and external binary dependencies without installing or upgrading them as a side effect.

Acceptance:

- Dependency versions and startup prerequisites are explicit.
- Local setup does not require cloud absolute paths.

### Step 2: Test harness and fixtures

Create platform test conventions and sanitized fixtures for Console messages, tool calls, artifacts, and final responses.

Acceptance:

- Tests run without private sessions or credentials.
- Baseline behavior is captured before adapters are introduced.

### Step 3: Unified message contract

Add a versioned normalized message model and a Console compatibility adapter. Do not migrate external channels yet.

Acceptance:

- Current Console behavior is reproducible through both old and normalized paths.
- Agent and Skills receive no provider-specific payloads from the new path.

### Step 4: AgentScope boundary adapter

Wrap the existing AgentScope invocation and output behavior behind a small platform-owned adapter.

Acceptance:

- No AgentScope core code is copied or modified.
- Adapter parity tests cover success, tool use, cancellation, and error mapping.

### Step 5: Unified response stream

Introduce the response-event protocol with in-memory collection and Console rendering before enabling external channel streaming.

Acceptance:

- Collected stream output equals current final output.
- Buffered fallback and terminal-event rules are tested.

### Step 6: Tool Router facade

Add a common routing facade for built-in tools, MCP clients, and existing Skills. Initially delegate to current implementations.

Acceptance:

- Existing Tool and Skill behavior is unchanged.
- Policy, timeout, cancellation, trace, and normalized errors are enforced at the facade.

### Step 7: Skill standard adoption

Migrate one low-risk Skill, recommended `file_reader`, to the manifest/schema/executor/test standard while keeping `SKILL.md` compatibility.

Acceptance:

- Old and new invocation paths pass the same fixtures.
- No other Skill directory changes.

PDF Editor requires its own later plan with its existing regression and visual-validation suite available before any structural change.

### Step 8: Channel adapters

Migrate channels in the order Console, Telegram, WeCom, then WeChat customer service. Each channel is disabled by default until its end-to-end suite passes.

Acceptance per channel:

- Inbound normalization.
- Identity and conversation mapping.
- Deduplication and ordering.
- Text and artifact delivery.
- Streaming or buffered fallback.
- Credential injection and redacted logs.
- Health check and rollback runbook.

## 7. Rollback strategy

Each migration unit uses an explicit compatibility switch or caller-level cutover. Rolling back means routing the affected caller to the existing path; it must not require restoring deleted files or reconstructing runtime data.

No existing path is removed in the same release that introduces its replacement.

## 8. Verification gates

Before every migration commit:

- working tree scope matches the approved unit;
- no credential or private runtime file is staged;
- existing relevant regression tests pass;
- new contract tests pass;
- configuration changes are schema validated;
- old and new behavior parity is recorded;
- rollback procedure is documented and exercised where practical.
