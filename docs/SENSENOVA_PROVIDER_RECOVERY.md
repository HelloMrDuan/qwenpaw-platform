# SenseNova Provider Recovery

> Phase: 17.5
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
self-contained release import are verified offline with mocked transport.

No SenseNova credential is present on the current machine. The real prompt
`a futuristic industrial control room, cinematic lighting` was therefore not
submitted, and the real test result is `PROVIDER_NOT_CONFIGURED`. This is not a
generation success claim. Real tenant installation, Tool enablement, API billing,
content-safety response, and Channel rendering still require controlled staging
acceptance.
