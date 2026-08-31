# SenseNova Provider Recovery

> Phase: 17.6.1
>
> Historical export result: `sn_agent_runner.py = NOT_FOUND`

## 1. Deterministic recovery result

Both retained exports and all repository Git refs were inspected by exact path
and content signature:

| Source | `sn_agent_runner.py` | SenseNova HTTP implementation |
| --- | --- | --- |
| `channel-runtime-recovery-export.zip` (3,533 entries) | `NOT_FOUND` | `NOT_FOUND`; only Hermes provider abstractions and call sites |
| `qwenpaw-platform-export.zip` | `NOT_FOUND` | `NOT_FOUND` |
| current working tree/recovered/backups/legacy | `NOT_FOUND` | historical call sites only |
| all local Git refs/path history | `NOT_FOUND` | no deleted tracked runner recovered |

The historical call sites nevertheless prove these command arguments:

```text
sn_agent_runner.py sn-image-generate
  --prompt ...
  --image-size 2k
  --aspect-ratio 1:1 or 16:9
  --save-path ...
  -o json
```

They also prove the model name `sensenova-u1-fast`, up to two Gateway retries,
local file output, and Secret injection from an external `.env`.

## 2. Authoritative implementation source found

The missing implementation remains publicly available in the official
[OpenSenseNova/SenseNova-Skills](https://github.com/OpenSenseNova/SenseNova-Skills)
repository. The recovery audit used upstream commit
`98a8bde28092fb8f33664154a0edeb4d9cdb352f`.

The upstream runner SHA-256 at that commit is:

```text
7516288C9C3BD3C2F8DD8A20022526CBBCB4DF7FC3F34D6C08AF6B547C59536A
```

That upstream source is MIT licensed. It was inspected as protocol evidence;
the full runner was not copied into a recovered historical directory because it
was not present in either original export and cannot be represented as the
byte-identical historical deployment file.

## 3. Recovered protocol

The official upstream `SensenovaText2ImageClient` confirms:

- default base URL: `https://token.sensenova.cn/v1`;
- endpoint: `POST /images/generations`;
- authentication: `Authorization: Bearer <API key>`;
- default model: `sensenova-u1-fast`;
- request: `model`, `prompt`, pixel `size`, URL response, PNG output, watermark
  flag; this implementation additionally passes optional negative prompt,
  seed, and count;
- synchronous response: OpenAI-style `data[].url`;
- output: download URL, verify complete image, atomically save local file;
- errors: explicit missing-key, HTTP/auth, empty response, download, and image
  decode failures.

The current upstream backend accepts `image_size` buckets `1K` and `2K` and
ten ratios: `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `1:1`, `16:9`, `9:16`,
and `9:21`. Although the generic runner exposes a `4k` option and mentions
`21:9`, the SenseNova backend at audited commit
`98a8bde28092fb8f33664154a0edeb4d9cdb352f` rejects 4K and ratios wider than
16:9; they are not advertised by this Tool.

The v1.0.1 adapter therefore translates ratio plus preset to the official exact
pixel bucket internally. Arbitrary pixel strings are no longer sent directly
to SenseNova. Non-native exact final sizes are handled after generation by
image-toolkit and retain full requested/provider/final provenance.

The historical runner exposed polling arguments, but the recovered upstream
SenseNova U1 client currently returns synchronous image data. The new adapter
also accepts an asynchronous `task_id` response with bounded polling for
gateway compatibility. A custom status URL can be injected through
`SENSENOVA_STATUS_URL_TEMPLATE`; otherwise it uses the generation endpoint plus
the task ID.

## 4. Configuration migration

Primary production names:

- `SENSENOVA_API_KEY`
- `SENSENOVA_BASE_URL`
- `SENSENOVA_IMAGE_MODEL`

Historical aliases remain accepted in descending priority:

- `SN_IMAGE_GEN_API_KEY` → `SN_API_KEY`
- `SN_IMAGE_GEN_BASE_URL` → `SN_BASE_URL`
- `SN_IMAGE_GEN_MODEL`

Optional bounded-operation variables are `SENSENOVA_TIMEOUT`,
`SENSENOVA_POLL_INTERVAL`, `SENSENOVA_MAX_RETRIES`, and
`SENSENOVA_STATUS_URL_TEMPLATE`.

## 5. Recovery versus validation

The Provider contract, SenseNova adapter, QwenPaw Tool Plugin registration,
download validation, Artifact conversion, error semantics, polling, and
self-contained release import, terminal ToolChunk/DataBlock result, exact-size
post-processing, and request/tool-call idempotency are verified offline with
mocked transport.

No SenseNova credential is present on the current machine, so this offline fix
did not submit a paid prompt. The existing cloud deployment has generated a
real image according to the supplied Phase 17.6.1 acceptance feedback; that
evidence exposed the unsupported-size and repeated-call defects. It does not
validate the v1.0.2 Schema-hotfix package. v1.0.2 tenant installation, Tool-call count,
exact-size output, final UI rendering, and Agent stop behavior still require
controlled staging acceptance.
