# Final Extension Strategy

> Baseline: QwenPaw v2.1.0  
> Decision point: Phase 13.0  
> Status: `AUTHORITATIVE`

## 1. Final capability strategy

| Capability | Final classification | Production/default path | Repository treatment |
| --- | --- | --- | --- |
| Telegram | `BUILTIN` | QwenPaw v2.1.0 built-in Telegram Channel | Historical Adapter, Plugin and Bridge are `LEGACY / FALLBACK / REFERENCE ONLY` |
| WeCom / 企业微信 | `BUILTIN` | QwenPaw v2.1.0 built-in WeCom Channel | Historical Adapter, Plugin and Bridge are `LEGACY / FALLBACK / REFERENCE ONLY` |
| WeChat / 微信 | `BUILTIN` | QwenPaw v2.1.0 built-in WeChat Channel | Configure and validate in Runtime; do not create a duplicate Channel |
| WeChat Customer / 微信客服 | `CUSTOM` (`CUSTOM REQUIRED`) | Preserve a separate open-kfid Gateway/Adapter boundary if the capability is retained | No BaseChannel or new Plugin is authorized in this phase |
| Hermes | `ARCHIVED / REFERENCE ONLY` | Never deploy or start as a production Runtime | Preserve selected lifecycle, concurrency, Skill orchestration, memory/context and session modules as reference only |
| PDF Editor | `CUSTOM` (`CUSTOM SKILL`) | Versioned Skill package uploaded through the supported QwenPaw/AgentScope Skill path | Continue independent Skill lifecycle and regression discipline |
| Image generation | `CUSTOM TOOL` (`OFFLINE READY`) | QwenPaw `image_generation` Tool Plugin -> provider-neutral Runtime -> remote SenseNova API | No Hermes dependency or parallel processing Skill; real tenant/API validation pending |

`LEGACY` applies to the historical Telegram/WeCom custom assets, not to the
Telegram or WeCom capabilities themselves. Their production capabilities are
`BUILTIN`.

## 2. Production architecture

```text
Telegram ---------------------------> QwenPaw built-in Channel
WeCom ------------------------------> QwenPaw built-in Channel
WeChat -----------------------------> QwenPaw built-in Channel

WeChat Customer open-kfid
  -> external Gateway (cursor/DB/dedup owner)
  -> custom Adapter boundary
  -> QwenPaw/Extension message boundary

PDF request
  -> QwenPaw Agent
  -> custom PDF Editor Skill

Hermes recovered platform
  -> reference/evaluation source only
  -> no competing production Runtime
```

## 3. What remains active

### Built-in configuration work

- Telegram, WeCom and WeChat configuration, staging acceptance, access control,
  media/streaming behavior, and operational monitoring belong to QwenPaw
  Runtime operations.

### Custom Extension work

- PDF Editor remains a supported custom Skill.
- WeChat Customer remains a separate custom integration requirement, but its
  recovered Gateway is not declared production-ready and no implementation work
  is approved by this analysis.

### Reference-only work

- Hermes selected modules may inform future design after a verified QwenPaw gap.
- Historical Telegram/WeCom Adapters, Plugins, bridges and packages remain for
  recovery evidence, regression protection, and fallback research only.

## 4. Decisions that are closed

- Do not develop Telegram `BaseChannel` or custom production registration.
- Do not develop WeCom `BaseChannel` or custom production registration.
- Do not treat built-in WeChat as equivalent to WeChat Customer.
- Do not deploy Hermes as a replacement for QwenPaw/AgentScope Runtime.
- Do not delete recovered assets or their offline tests.
- Do not move cursor or database ownership from the WeChat Customer Gateway into
  an Adapter, Agent, or Skill.

## 5. Decisions requiring a future authorized phase

| Topic | Required evidence before implementation |
| --- | --- |
| WeChat Customer deployment | Supported extension entry, sanitized configuration, dependency lock, Gateway recovery, cursor/dedup rollback proof, staging tenant validation |
| Hermes capability extraction | Reproducible QwenPaw gap, minimal non-Runtime Extension boundary, license/security review, isolated tests |
| Built-in Channel exception | Reproducible deficiency in the exact QwenPaw version/tenant plus explicit approval to reopen custom Channel work |
| Image-generation production acceptance | Install/enable Tool Plugin, inject Secret, validate billing/content safety, Artifact rendering, and real Channel response in staging |

## 6. Source decisions

Detailed evidence is recorded in:

- `docs/QWENPAW_CHANNEL_STRATEGY.md`
- `docs/HERMES_FIT_GAP_ANALYSIS.md`
- `docs/WECHAT_CUSTOMER_FIT_GAP_ANALYSIS.md`

This strategy supersedes earlier planning documents wherever they describe
Telegram or WeCom as future production custom Plugins, Hermes as an active
Runtime candidate, or WeChat Customer as merely equivalent to built-in WeChat.
