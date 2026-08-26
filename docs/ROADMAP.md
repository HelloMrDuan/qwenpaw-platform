# QwenPaw Platform Roadmap

## Roadmap rules

- Each phase must leave existing runtime assets intact.
- A later phase cannot begin until the previous phase has explicit acceptance evidence.
- Interfaces are introduced before implementations are moved.
- AgentScope core remains an external runtime dependency, not a rewrite target.
- Credentials, conversations, and generated artifacts stay outside Git.

## Phase 1: Platform foundation cleanup

Goal: turn the imported workspace into an understandable and governable engineering repository.

Deliverables:

- Architecture, current-status, channel, streaming, Skill, and migration documentation.
- Stable top-level directory skeleton: `apps/`, `core/`, `channels/`, `skills/`, `configs/`, `docs/`, `tests/`.
- Sensitive-data scan and explicit Git ignore policy.
- Inventory of existing channels, Skills, MCP drivers, and runtime state.
- Baseline commit that does not modify business logic.

Exit criteria:

- Documentation reflects actual configuration rather than export claims alone.
- Existing Skills and agent configuration remain byte-for-byte untouched by Phase 1.
- Git contains no detected credential material or private runtime data.

## Phase 2: Unified message model

Goal: define one versioned internal message contract independent of channel providers.

Deliverables:

- `NormalizedMessage` and content-part schemas.
- Stable identity, conversation, reply, attachment, trace, and capability fields.
- Console adapter as the reference implementation.
- Contract fixtures for text, image, file, voice metadata, and reply context.
- Compatibility adapter from the normalized model to the existing AgentScope input.

Exit criteria:

- Console messages pass through normalization without behavior regression.
- Channel-specific payloads do not enter Agent or Skill APIs.
- Schema compatibility and malformed-input tests pass.

## Phase 3: Streaming output refactor

Goal: expose one response-event stream while allowing channels to choose streaming, message editing, or buffering.

Deliverables:

- Versioned response-event envelope.
- Lifecycle, delta, tool, artifact, warning, completion, cancellation, and error events.
- Sequence ordering, backpressure, timeout, and cancellation rules.
- Console reference renderer.
- Buffered fallback for channels without native streaming.

Exit criteria:

- The same agent execution can feed both a streaming renderer and a buffered renderer.
- Tool events and final content remain ordered and traceable.
- Existing PDF Editor progress events can be adapted without changing PDF Editor.

## Phase 4: Tool system expansion

Goal: give built-in tools, MCP tools, and Skills one governed routing and execution contract.

Deliverables:

- Tool descriptor and invocation schemas.
- Capability discovery and policy enforcement.
- Timeout, retry, cancellation, artifact, and normalized-error handling.
- Incremental Skill manifest adoption.
- Word, Excel, PPT, OCR, image, and future video capability plans based on shared contracts.

Exit criteria:

- A caller can discover and invoke tools without knowing whether they are built-in, MCP, or Skill backed.
- Every invocation has schema validation, policy evaluation, traceability, and test coverage.
- Existing Skills continue to load through a compatibility path.

## Phase 5: Multi-channel productionization

Goal: bring priority channels to reliable production operation on shared contracts.

Production strategy:

1. Console reference channel.
2. Configure and accept the built-in Telegram Channel.
3. Configure and accept the built-in WeCom / 企业微信 Channel.
4. Configure and accept the built-in WeChat / 微信 Channel.
5. Verify WeChat Customer separately; do not equate its Gateway/cursor/database
   chain with built-in 微信.
6. Verify Hermes only if an independent production role remains.

Deliverables:

- Built-in Channel configuration and acceptance evidence for Telegram, WeCom,
  and WeChat; no replacement `BaseChannel` development.
- Legacy Telegram/WeCom Adapter, Plugin, and Bridge assets retained as
  `LEGACY / FALLBACK / REFERENCE ONLY`.
- A separate capability decision for WeChat Customer before any custom work.
- Credential injection, webhook or socket lifecycle, idempotency, and rate-limit handling.
- Health checks, structured logs, metrics, replay fixtures, and deployment runbooks.
- End-to-end tests for inbound text, attachments, tool use, error fallback, and outbound delivery.

Exit criteria:

- Each production channel has an owner, runbook, health signal, rollback path, and passing end-to-end suite.
- No channel requires changes inside AgentScope core.
