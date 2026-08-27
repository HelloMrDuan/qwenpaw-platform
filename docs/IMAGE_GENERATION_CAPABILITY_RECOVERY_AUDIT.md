# Existing Image Generation Capability Recovery Audit

> Phase: 17.4
>
> Conclusion: `CASE E`
>
> Scope: repository/export audit and routing-boundary correction only

> Phase 17.5 update: an independent SenseNova Tool Provider is now implemented
> and packaged offline; real QwenPaw tenant/API validation remains pending.

## 1. Definitive conclusion

The historical “生成一张……” capability was not an independently recovered
QwenPaw/AgentScope built-in capability. The deployed Channel paths called an
external SenseNova image runner directly from the historical Hermes/Bridge or
WeChat Customer Gateway layer. The referenced `sn_agent_runner.py`, its
provider implementation, credentials, and provider environment were not
included in either export and are not registered by the current QwenPaw
workspace.

The result is therefore **CASE E**: historical image generation existed in the
Hermes/Bridge/Gateway estate, while the current QwenPaw workspace has no
independent image-generation implementation. A missing third-party runner and
provider configuration are contributing recovery gaps, but configuration alone
cannot restore a Tool that is not present or registered.

No new Skill, Runtime, model, provider, or external API call was introduced by
this audit.

## 2. Evidence inventory

| Evidence | Finding |
| --- | --- |
| `plugins/hermes/recovered/fast_route.py` | Routes `image` intent, emits Telegram progress, invokes `sn_agent_runner.py sn-image-generate`, then sends a photo or failure text |
| `adapters/telegram/recovered/telegram_bridge_main.py` | Sends Telegram input to the historical `run_image_and_reply.sh`/fast-route path |
| `plugins/wecom/recovered/wecom-node/wecom_bridge.mjs` | Classifies image intent, sends streaming progress, directly invokes the same runner, uploads the result to WeCom |
| `plugins/wechat-customer/recovered/wecom_kf_gateway_v345.py` | Uses QwenPaw only to return `mode=image` JSON; the Gateway then calls the external runner, prepares/uploads the image, sends it, and records state in SQLite |
| `plugins/hermes/recovered/hermes-agent-main/agent/image_gen_provider.py` | Contains an independent Hermes provider abstraction for an `image_generate` Tool |
| `plugins/hermes/recovered/hermes-agent-main/agent/image_gen_registry.py` | Requires a provider plugin to register at import time; no matching recovered provider is active in this repository |
| `configs/agent.json` | Registers file, web, image-view, and other QwenPaw built-ins, but no `image_generate`, `image_generation`, or equivalent Tool |
| `configs/skill.json` | Contains no historical image-generation Skill |
| both export ZIPs | Preserve references and recovered bridge/gateway source, but not `sn_agent_runner.py` or its provider environment |

Evidence hashes used during the audit:

- `qwenpaw-platform-export.zip`: `81CD75D1635BD18A1255D821CA931BECEF81CDB2ED1AF7884895A797743B95ED`
- `channel-runtime-recovery-export.zip`: `35FD917257B4BCB0862D7A76EF296985D265BC7A70F359601F2748E603AA8300`
- `configs/agent.json`: `C2CDEB8E5E207C26E6475E763FE28BEDE3B6986278B813ED7C4643CCB9FB849C`

## 3. Category decision

| Candidate | Decision | Evidence-based reason |
| --- | --- | --- |
| A. QwenPaw built-in | Not found | Current exported built-in registry has image viewing but no image generator |
| B. AgentScope built-in | Not found | No exported configuration, Tool registration, or source reference proves an AgentScope built-in generator |
| C. Historical Plugin | Partial source evidence only | Hermes defines a provider plugin interface, but no deployed provider plugin was recovered |
| D. Historical Skill | Not found | No generation Skill exists in the exported Skill registry |
| E. Runtime Tool | Historical Hermes abstraction only | `image_generate` belongs to the recovered alternate Hermes Runtime, not current QwenPaw |
| F. Third-party API | Confirmed dependency | Historical production paths reference SenseNova through the missing runner |
| G. Hermes/Bridge | Confirmed deployed integration layer | Telegram, WeCom, and WeChat Customer paths invoked the runner outside QwenPaw Tool execution |

The single required final classification remains `CASE E`.

## 4. Historical request chains

### WeChat Customer production path

```text
WeChat Customer message
  -> Gateway ACK + cursor/session/dedup DB
  -> QwenPaw public Agent classifies only
  -> {"mode":"image","prompt":"..."}
  -> Gateway invokes sn_agent_runner.py sn-image-generate
  -> SenseNova U1 Fast
  -> local PNG
  -> image preparation/compression
  -> WeCom media upload
  -> image send + generated_images DB state
```

### Historical Telegram path

```text
Telegram update
  -> recovered polling bridge
  -> run_image_and_reply.sh / fast_route.py
  -> "正在生成图片…"
  -> sn_agent_runner.py sn-image-generate
  -> local PNG
  -> Telegram sendPhoto("生成完成") or failure text
```

### Historical WeCom bridge path

```text
WeCom frame
  -> semantic route=image
  -> replyStream("正在生成图片…")
  -> sn_agent_runner.py sn-image-generate
  -> replyStream("图片已生成，正在发送…")
  -> media upload/send or streamed failure
```

Hermes also contains a source-level `image_generate` provider abstraction, but
the provider implementation/registration needed to run it was not recovered.
It must not be confused with the direct runner path above or with a current
QwenPaw built-in capability.

## 5. Current request chain and break

```text
QwenPaw built-in Channel
  -> QwenPaw Agent
  -> exported built-in Tool registry (no generator)
  -> Skill selection (four image-processing Skills only)
  -> no image-generation provider or Tool
  -> no generated-image result
```

The first hard break is capability discovery: no generator is registered. The
next missing nodes are the runner/provider and their external configuration.
There is consequently no successful generation result for Artifact or Channel
delivery to consume.

## 6. Routing-boundary correction

`image-toolkit`, `photo-restoration`, `image-background-tools`, and
`image-quality-enhancer` all operate on an existing image. Their earlier
descriptions did not state that prerequisite strongly enough, so a semantic
router could treat them as candidates for a new-image request.

Their published descriptions now require an existing input image and explicitly
exclude text-to-image/new-image creation. No executor or processing behavior was
changed. “生成一张赛博朋克城市图片” is reserved for an image-generation
capability and must not fall through to one of these four Skills.

## 7. Artifact and progress boundaries

The current Artifact contract can represent `image/png` and `image/jpeg`, a
path/URI, SHA-256 checksum, size, width, and height. It is not the break. The
historical deployed paths predated that contract and delivered a local file
through Telegram/WeCom media upload.

The Extension streaming model still supports `tool.start`, `tool.progress`,
`file.created`, `tool.result`, and error events. Historical Telegram/WeCom code
also contains real progress/success/failure messages. These are separate
systems: the local Extension stream has not been proven to be consumed by the
QwenPaw cloud Runtime. Phase 17.5 adds a Provider progress callback and final
Tool status, but the documented QwenPaw `register_tool` API does not expose a
cloud progress callback, so no streaming claim is made.

## 8. Recovery boundary

At the Phase 17.4 baseline, “生成一张……” was not restored. Phase 17.5 found the
official OpenSenseNova implementation source, implemented a provider-neutral
Runtime and SenseNova adapter, and added an official QwenPaw
`PluginApi.register_tool("image_generation")` entry. This restores the local
registration and execution chain without Hermes. Real tenant installation and
API validation still require a Secret and staging acceptance.

The offline tests verify the published routing contract for the five required
prompts and verify that the current exported built-in registry has no generator.
They do not claim a live QwenPaw cloud routing or generation test. See
`docs/IMAGE_GENERATION_RUNTIME.md` and `docs/SENSENOVA_PROVIDER_RECOVERY.md`.
