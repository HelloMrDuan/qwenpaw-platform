# SenseNova Size and Idempotency Contract

> Phase: 17.6.1  
> Audited upstream: OpenSenseNova/SenseNova-Skills commit
> `98a8bde28092fb8f33664154a0edeb4d9cdb352f`

## Official provider abstraction

The SenseNova backend accepts `1K` and `2K`. The QwenPaw Tool exposes the
normalized lower-case values `1k` and `2k`; the default is `2k`. Supported
ratios are:

`2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `1:1`, `16:9`, `9:16`, `9:21`.

`4k` and `21:9` are not exposed. They appear in generic upstream runner
surfaces but are rejected by the audited SenseNova backend.

## Exact provider mapping

| Ratio | 1K provider size | 2K provider size |
| --- | --- | --- |
| 2:3 | 1088x1632 | 1664x2496 |
| 3:2 | 1632x1088 | 2496x1664 |
| 3:4 | 1152x1536 | 1760x2368 |
| 4:3 | 1536x1152 | 2368x1760 |
| 4:5 | 1184x1472 | 1824x2272 |
| 5:4 | 1472x1184 | 2272x1824 |
| 1:1 | 1344x1344 | 2048x2048 |
| 16:9 | 1792x992 | 2752x1536 |
| 9:16 | 992x1792 | 1536x2752 |
| 9:21 | 864x2048 | 1344x3136 |

Source evidence:
[official SenseNova backend](https://github.com/OpenSenseNova/SenseNova-Skills/blob/98a8bde28092fb8f33664154a0edeb4d9cdb352f/skills/sn-image-base/scripts/sn_image_base/generation/sensenova.py).

## Tool contract and policy

The public Tool accepts `prompt`, constrained `aspect_ratio`, constrained
`image_size`, optional `requested_size`, `fit_mode`, and ordinary generation
options. It does not accept arbitrary `width` and `height` provider buckets.

- no size/ratio: `2k`, `16:9`;
- “横屏”/landscape: configured landscape ratio, default `16:9`;
- “竖屏”/portrait: configured portrait ratio, default `9:16`;
- exact native size: use its native bucket directly;
- exact non-native final size: choose the same or nearest supported ratio,
  generate one native bucket, then use image-toolkit;
- `require_native_size=true`: reject a non-native exact size before any remote
  call, with non-retryable `INVALID_IMAGE_SIZE` plus
  `supported_image_sizes` and `supported_aspect_ratios`.

The default `cover` policy preserves aspect ratio and center-crops. `contain`
preserves the full image with padding. `stretch` exists only as an explicit
opt-in and is never the default.

## Result provenance

Both the generation response and Artifact metadata distinguish:

- `requested_size`, `requested_aspect_ratio`;
- `image_size`;
- `provider_size`, `provider_aspect_ratio`;
- `final_size`.

For `1920x1080`, the default flow is:

```text
requested_size=1920x1080
requested_aspect_ratio=16:9
provider_size=2752x1536
provider_aspect_ratio=16:9
image-toolkit fit_mode=cover
final_size=1920x1080
```

## Terminal result and idempotency

QwenPaw v2.1.0 official image Tool plugins return
`ToolChunk(ToolResultState.SUCCESS)` with a local image `DataBlock` and a
`TextBlock`. This adapter follows that contract and adds an explicit completed
summary. The image Artifact remains intact and its MIME, URI, and checksum are
preserved.

The Plugin uses an official `on_acting` middleware to capture `tool_call.id`
and the latest user message ID. A durable record is keyed by tool call and by
user turn plus canonical request fingerprint. A completed result is reused only
while every Artifact exists and passes SHA-256 validation. Retryable failures
are never cached, while deterministic failures prevent an Agent size-guessing
loop.

The official contract evidence is the
[QwenPaw v2.1.0 Plugin documentation](https://github.com/agentscope-ai/QwenPaw/blob/v2.1.0/website/public/docs/plugins.en.md)
and the
[official GPT Image Tool implementation](https://github.com/agentscope-ai/QwenPaw/blob/v2.1.0/plugins/tool/gpt-image2/gpt_image2_tool.py).

## Validation boundary

Offline tests verify one provider call for a normal successful request, no
second provider call for a completed duplicate, final 1920x1080 pixels, image
DataBlock construction, clean terminal success, and retry semantics. QwenPaw
cloud v1.0.1 upload, actual Chat UI rendering, final Agent stop behavior, and
cloud Tool-call count remain `NOT EXECUTED / TO VERIFY`; local return values do
not prove those UI outcomes.
