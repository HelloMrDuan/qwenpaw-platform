# Current Platform Status

## 1. Baseline

- Workspace source: QwenPaw Cloud Workspace export dated 2026-08-24.
- Imported Git baseline: `1acb163939ef17bab2481c900d384b8db7a05dad`.
- Runtime framework: QwenPaw with AgentScope.
- Agent ID: `default`.
- Backend: `qwenpaw`.
- Language: Chinese (`zh`).
- Approval level: `AUTO`.
- Current configured model: `kilo-auto/free`.

The repository contains an imported runtime workspace, not yet a locally reproducible application distribution. Cloud absolute paths and external dependencies still need controlled migration.

## 2. Channels

| Channel | Configuration present | Enabled in `configs/agent.json` | Local implementation evidence |
| --- | --- | --- | --- |
| Console | Yes | Yes | Native runtime channel; current default |
| Telegram | Yes | No | Historical bridge evidence exists; bridge source is not in this export |
| WeCom / 企业微信 | Yes | No | Operational scripts and runbooks exist; production gateway source is not in this export |
| WeChat / 微信 | Yes | No | Configuration block and historical documentation exist; no standalone adapter source was exported |

Additional disabled configuration blocks exist for iMessage, Discord, DingTalk, Feishu, QQ, Mattermost, MQTT, Matrix, Voice, SIP, Xiaoyi, Yuanbao, Slack, and OneBot.

The presence of a configuration block does not mean the channel is production-ready. A channel becomes supported only after credentials, connectivity, message normalization, reply delivery, error handling, and end-to-end tests are verified.

## 3. Existing Skills

The imported workspace contains 17 Skills:

1. `QA_source_index`
2. `browser`
3. `channel_message`
4. `chat_with_agent`
5. `cron`
6. `dingtalk_channel`
7. `docx`
8. `file_reader`
9. `guidance`
10. `himalaya`
11. `make-skill`
12. `make_plan`
13. `multi_agent_collaboration`
14. `pdf`
15. `pdf-editor`
16. `pptx`
17. `xlsx`

Capability groups:

- Documents: PDF, PDF Editor Production V1.1, DOCX, PPTX, XLSX.
- Agent collaboration: chat, multi-agent collaboration, planning, Skill creation.
- Operations: cron, channel messaging, browser automation, file reading, email.
- Guidance and knowledge routing: guidance and QA source index.
- Channel onboarding: DingTalk channel connection Skill.

## 4. PDF and OCR status

`pdf-editor` is an existing production-oriented deterministic PDF editing Skill with scoped text edits, page operations, image operations, merge/split/extract, visual validation, and progress events. It must remain unchanged during platform baseline work.

The general PDF Skill documents OCR workflows. PDF Editor V1.1 can classify scanned candidates but does not provide an OCR repaint editing engine. OCR editing remains a future, separately testable capability.

## 5. MCP and tools

- Tavily Search MCP driver is present under `drivers/mcp/`.
- Transport: `stdio`.
- Command: `npx -y tavily-mcp@latest`.
- Current state: disabled.
- Credential value in the active exported configuration: empty.
- Default driver policy: deny, with explicit ask rules.

The platform also has built-in tool configuration for shell, file operations, code execution, and image viewing. A standalone image-generation Skill was not included in the export.

## 6. Configuration inventory

| Configuration | Purpose | Git policy |
| --- | --- | --- |
| `configs/agent.json` | Agent, channels, model routing, tools, security | Versioned; secret fields must remain empty |
| `configs/skill.json` | Skill registry | Versioned |
| `configs/.mcp` | MCP migration marker/config | Versioned |
| `drivers/mcp/*.yaml` | MCP driver definitions | Versioned only when credentials are referenced, not embedded |
| `configs/credentials.yaml` | Local credentials | Ignored |
| `configs/chats.json` | Runtime chat index | Ignored |
| `configs/jobs.json` | Runtime jobs | Ignored |
| `configs/PROFILE.md` | User-specific profile | Ignored |
| `configs/MEMORY.md` | User-specific memory settings | Ignored |

## 7. Runtime data

The following structures are preserved locally and excluded from Git because they contain private conversations, credentials, runtime state, or derived indexes:

- `memory/`
- `sessions/`
- `mem_agent/`
- `mem_metadata/`
- `mem_session/`
- `checkpoints/`
- original cloud export archives

## 8. Known gaps

- QwenPaw CLI and all runtime dependencies are not packaged by this baseline.
- Cloud Linux/NAS absolute paths remain in exported configuration and scripts.
- Telegram, WeCom, and WeChat channel source is not present in `channels/`.
- No unified internal message model exists in this repository yet.
- No shared response-stream contract exists yet.
- No platform-level test harness exists yet.
- No dependency lockfile or reproducible local runtime setup has been established.
