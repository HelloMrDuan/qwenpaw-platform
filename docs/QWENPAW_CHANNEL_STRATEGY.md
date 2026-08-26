# QwenPaw Channel Strategy

> Status: `AUTHORITATIVE`  
> Effective baseline: QwenPaw v2.1.0 Console verification  
> Decision: stop custom Telegram and WeCom production Channel development.

## 1. Final strategy

| Capability | Production strategy | Repository role |
| --- | --- | --- |
| Telegram | `BUILTIN` | Configure and accept the QwenPaw v2.1.0 built-in Channel |
| WeCom / 企业微信 | `BUILTIN` | Configure and accept the QwenPaw v2.1.0 built-in Channel |
| WeChat / 微信 | `BUILTIN` | Configure and accept the QwenPaw v2.1.0 built-in Channel |
| WeChat Customer / 微信客服 | `CUSTOM / TO VERIFY` | Preserve the historical Gateway boundary and verify whether a custom integration is still required |
| PDF Editor | `CUSTOM SKILL` | Continue using the versioned Skill release and Workspace upload path |
| Hermes | `TO VERIFY` | Retain recovered assets until its independent production role is proven |

This table is the default production-routing decision. Earlier documents that
describe Telegram or WeCom custom `BaseChannel` implementation as a future step
are historical records and are superseded by this strategy.

## 2. Verified built-in Channel capabilities

The QwenPaw v2.1.0 Console confirms that Telegram, 企业微信, and 微信 are built-in
Channels. Production setup must use those built-in entries unless a later,
explicit architecture decision records a verified capability gap.

Telegram's built-in Channel already owns:

- Bot Token configuration;
- proxy configuration;
- streaming output;
- typing status;
- access control;
- provider connection and Channel lifecycle.

The built-in 企业微信 Channel already owns:

- Bot ID and Secret configuration;
- QR-code authorization;
- media directory configuration;
- group-chat context;
- provider connection and Channel lifecycle.

The built-in 微信 Channel uses the QwenPaw-supported QR-code login/Bot Token
model. Its exact staging configuration and acceptance remain Runtime operations,
not Extension implementation work.

## 3. Development decisions

The following production development is stopped:

- Telegram `BaseChannel` implementation;
- WeCom `BaseChannel` implementation;
- Telegram custom Channel registration;
- WeCom custom Channel registration;
- production packaging or deployment of the recovered Telegram/WeCom bridges
  as replacements for built-in Channels.

Allowed maintenance is limited to:

- preserving and documenting recovered assets;
- offline regression tests that protect historical behavior and hashes;
- forensic comparison, rollback research, and disaster-recovery reference;
- migration documentation that explicitly retains the legacy classification.

No legacy asset is deleted by this decision.

## 4. Legacy and fallback asset classification

The following paths are `LEGACY / FALLBACK / REFERENCE ONLY`:

| Path or asset | Classification | Production default |
| --- | --- | --- |
| `adapters/telegram/` | `LEGACY / FALLBACK / REFERENCE ONLY` | Do not deploy; use built-in Telegram |
| `plugins/telegram-channel-plugin/` | `LEGACY / FALLBACK / REFERENCE ONLY` | Do not continue custom Channel registration |
| historical Telegram Bridge | `LEGACY / FALLBACK / REFERENCE ONLY` | Preserve source and hashes only |
| `adapters/wecom/` | `LEGACY / FALLBACK / REFERENCE ONLY` | Do not deploy; use built-in 企业微信 |
| `plugins/wecom-channel-plugin/` | `LEGACY / FALLBACK / REFERENCE ONLY` | Do not continue custom Channel registration |
| historical WeCom Bridge | `LEGACY / FALLBACK / REFERENCE ONLY` | Preserve source and hashes only |

Existing manifests, Plugin facades, package tests, Runtime Gateway tests, and
recovered sources remain in Git because they provide migration evidence and a
fallback reference. Passing those tests does not grant production-deployment
status.

## 5. WeChat Customer is a separate integration

QwenPaw's built-in “微信” entry must not be assumed equivalent to the historical
微信客服 Gateway. The historical business chain includes:

- `open_kfid` service-account identity;
- `external_userid` customer identity;
- polling/callback cursor ownership;
- an independently supervised Gateway;
- Gateway-owned database state;
- message deduplication, retry, and delivery state.

These semantics differ from a QR-code login/Bot Token personal or bot Channel.
Accordingly, WeChat Customer remains `CUSTOM / TO VERIFY`; it is not redirected
to built-in 微信 until evidence proves functional equivalence.

Verification must answer, without starting production services:

1. whether QwenPaw v2.1.0 exposes an official 微信客服/open-kfid Channel;
2. whether it preserves cursor, deduplication, session, and delivery semantics;
3. whether the historical Gateway database can remain its exclusive state owner;
4. whether a supported Plugin/API boundary exists if built-in coverage is absent;
5. whether staging rollback can preserve cursor and prevent duplicate delivery.

Until those questions are closed, no new WeChat Customer business logic or
Gateway replacement is authorized.

## 6. Deployment policy

```text
Telegram / WeCom / WeChat
        -> QwenPaw built-in Channel configuration
        -> staging acceptance
        -> production enablement

WeChat Customer
        -> capability verification
        -> architecture decision
        -> only then consider custom deployment

PDF Editor
        -> custom Skill package
        -> AgentScope/QwenPaw Skill upload
```

Telegram and WeCom custom Plugin ZIPs are historical validation artifacts, not
production candidates. They must not be selected merely because packaging or
isolated-import tests pass.

## 7. Acceptance and change control

Any future proposal to replace a built-in Channel must provide all of the
following before code work starts:

- a documented, reproducible built-in capability gap;
- QwenPaw version and tenant evidence;
- security and secret-management review;
- lifecycle, streaming, media, access-control, and rollback requirements;
- explicit approval to reopen custom Channel development.

Absent that evidence, the built-in implementation remains authoritative.
