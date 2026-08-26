# Hermes Fit-Gap Analysis

> Phase: 13.0  
> Decision: `PARTIAL KEEP`  
> Scope: source audit only; no Hermes, Bridge, Agent, Runtime, or Channel code was changed.

## 1. Executive conclusion

The recovered Hermes asset is a complete, independent Agent platform rather
than a small QwenPaw Channel extension. It contains its own Agent loop, gateway,
tool execution, skills, sessions, memory, cron, MCP, ACP, provider integrations,
CLI, deployment backends, and messaging support. Running it as a second
production Runtime beside QwenPaw would duplicate ownership of Agent execution,
tools, sessions, and Channels.

The Phase 15 final disposition supersedes the earlier `PARTIAL KEEP` label:
Hermes is now `ARCHIVED / REFERENCE ONLY`:

- keep selected Agent orchestration, tool-safety, Skill composition, memory,
  context, and session modules as design/reference assets;
- keep all recovered source intact for traceability;
- do not deploy `hermes-agent-main/` as the qwenpaw-platform Runtime;
- treat the historical Telegram/WeCom bridges and launch scripts as
  `LEGACY / FALLBACK / REFERENCE ONLY`;
- do not claim feature parity or copy code into QwenPaw until a separately
  approved, reproducible Runtime gap is demonstrated.

## 2. Evidence inventory

| Asset | Location | Observed responsibility | Finding |
| --- | --- | --- | --- |
| Hermes platform | `plugins/hermes/recovered/hermes-agent-main/` | Independent Agent, gateway, tools, skills, sessions, memory, cron, MCP, ACP, CLI and deployment platform | Full alternate Runtime; not an Extension-sized component |
| Telegram polling bridge | `adapters/telegram/recovered/telegram_bridge_main.py` | Telegram `getUpdates`, offset persistence, direct Bot API calls, route script invocation | Replaced in production by QwenPaw built-in Telegram |
| Alternate Telegram bridge | `adapters/telegram/recovered/telegram_bridge.py` | Telegram polling, allow-list, lock/offset files, `hermes.sh` invocation | Replaced in production by QwenPaw built-in Telegram |
| Telegram launcher | `adapters/telegram/recovered/start_bridge.sh` | PID/log/process launcher with historical absolute paths | Legacy operations artifact |
| WeCom launcher | `plugins/wecom/recovered/start_wecom_bridge.sh` | Starts the historical Node WeCom bridge with PID/log handling | Replaced in production by QwenPaw built-in WeCom |
| Fast router | `plugins/hermes/recovered/fast_route.py` | LLM classification into `image`, `infographic`, or `agent`, then direct Telegram delivery | Route taxonomy has reference value; implementation is legacy and incomplete |
| Image/agent runner | `sn_agent_runner.py` | Referenced by historical scripts for Agent/image execution | `NOT FOUND`; implementation and independent value cannot be verified |
| Historical Hermes launcher | `hermes.sh` | Referenced by bridges/router as the Hermes CLI entry | Historical external dependency; not recovered as the named script |

The recovered `fast_route.py` is not production-portable: it contains historical
absolute paths, reads an external environment file, couples routing to Telegram
delivery, and calls missing external runners. It must not be promoted as a
current router implementation.

## 3. Classification method

| Code | Meaning |
| --- | --- |
| A | QwenPaw v2.1.0 already provides the platform role or verified built-in capability |
| B | qwenpaw-platform already provides the relevant Extension-layer capability |
| C | Hermes contains an independently useful implementation or design pattern not proven equivalent elsewhere |
| D | Historical duplication, incomplete dependency chain, or obsolete production path |

`A` does not assert byte-for-byte feature parity. It means QwenPaw owns that
production responsibility. A Hermes implementation is marked `C` only when its
specific behavior remains useful for later gap evaluation.

## 4. Capability fit-gap matrix

| Hermes capability | Evidence | Classification | Decision |
| --- | --- | --- | --- |
| Telegram transport | Recovered polling bridges, offsets, allow-list and direct Bot API calls | A, D | Use QwenPaw built-in Telegram; preserve bridge source only |
| WeCom transport | Historical Node bridge and launcher | A, D | Use QwenPaw built-in WeCom; preserve bridge source only |
| Agent main loop and model/provider execution | `agent/`, `gateway/`, CLI and provider-facing modules | A, D | QwenPaw Runtime remains authoritative; do not introduce a second Agent Runtime |
| Agent/task routing | Agent loop and tool executor provide dispatch; `fast_route.py` adds a narrow image/infographic/agent classifier | A, C, D | Keep the general routing concepts for analysis; retire the hard-coded fast-route implementation |
| Multi-agent/task lifecycle | `agent/subagent_lifecycle.py` provides launch, status, wait, cancel, result and reconnect states; `delegate_task` is dispatched by the tool executor | A, C | Keep as reference for lifecycle semantics; do not wire it into Runtime in this phase |
| Tool routing and parallel safety | `agent/tool_dispatch_helpers.py` plans safe parallel/sequential segments and detects path overlap; `agent/tool_executor.py` handles execution and authorization | A, C | Keep as design/reference material for future verified tool-execution gaps |
| Skill discovery and invocation | `agent/skill_commands.py`, `skill_preprocessing.py`, `skill_bundles.py` scan, resolve, reload and compose Skills | A, B, C | QwenPaw owns production Skill execution and qwenpaw-platform owns manifests/packages; retain composition patterns only |
| Session and context | `gateway/session*.py`, `agent_cache_pressure.py`, context engine and compression modules | A, C | Keep reference modules for session rotation, cache pressure and compaction behavior |
| Memory lifecycle | `memory_manager.py`, `memory_provider.py` and compression hooks | C | Preserve for a future memory-gap study; no current integration authorized |
| Scheduled tasks | `cron/` scheduler, jobs and execution modules | A, C | QwenPaw already exposes scheduled tasks; keep Hermes code only as a comparison source |
| MCP and ACP | `optional-mcps/`, `mcp_serve.py`, `acp_adapter/` | A, D | Use QwenPaw built-in MCP/ACP boundaries; do not duplicate them |
| Terminal/deployment backends | Local/container/remote execution and packaging assets | D | Outside the Extension repository's production role |
| Self-improvement/user modeling claims | Hermes documentation and memory/Skill subsystems | C | Treat as unvalidated research/reference capability, not a production claim |

## 5. Modules to retain under `PARTIAL KEEP`

The following are the only modules currently identified as having independent
reference value. “Retain” means preserve and study, not import into QwenPaw:

### Multi-agent and task lifecycle

- `plugins/hermes/recovered/hermes-agent-main/agent/subagent_lifecycle.py`

### Tool routing and execution safety

- `plugins/hermes/recovered/hermes-agent-main/agent/tool_dispatch_helpers.py`
- `plugins/hermes/recovered/hermes-agent-main/agent/tool_executor.py`

### Skill discovery and composition

- `plugins/hermes/recovered/hermes-agent-main/agent/skill_commands.py`
- `plugins/hermes/recovered/hermes-agent-main/agent/skill_preprocessing.py`
- `plugins/hermes/recovered/hermes-agent-main/agent/skill_bundles.py`

### Memory and context management

- `plugins/hermes/recovered/hermes-agent-main/agent/memory_manager.py`
- `plugins/hermes/recovered/hermes-agent-main/agent/memory_provider.py`
- `plugins/hermes/recovered/hermes-agent-main/agent/context_engine.py`
- `plugins/hermes/recovered/hermes-agent-main/agent/context_compressor.py`
- `plugins/hermes/recovered/hermes-agent-main/agent/conversation_compression.py`

### Session and cache-pressure handling

- `plugins/hermes/recovered/hermes-agent-main/gateway/session.py`
- `plugins/hermes/recovered/hermes-agent-main/gateway/session_context.py`
- `plugins/hermes/recovered/hermes-agent-main/gateway/session_state.py`
- `plugins/hermes/recovered/hermes-agent-main/gateway/agent_cache_pressure.py`

The `cron/` implementation may remain as general reference, but no cron module
is placed on the active keep list because QwenPaw already exposes scheduled-task
management and no missing production behavior has been demonstrated.

## 6. Legacy-only assets

The following are not production candidates:

- both historical Telegram bridges and `start_bridge.sh`;
- `start_wecom_bridge.sh` and the historical WeCom bridge path;
- `fast_route.py` as executable production code;
- hard-coded NAS launchers and environment coupling;
- the full Hermes Agent loop as a replacement for QwenPaw Runtime;
- `sn_agent_runner.py` integration claims, because the file is not present.

No legacy file is deleted. The classification prevents accidental production
selection while retaining recovery evidence.

## 7. Re-entry criteria

A Hermes module may move beyond reference status only after a separate phase
provides:

1. a reproducible QwenPaw v2.1.0 capability gap;
2. an Extension boundary that does not replace the AgentScope/QwenPaw Runtime;
3. dependency, license, security, and state-ownership review;
4. isolated tests and rollback behavior;
5. explicit approval for implementation.

The final Hermes strategy is `ARCHIVED / REFERENCE ONLY`. No future production
role is planned; any reuse requires a new explicit architecture decision.
