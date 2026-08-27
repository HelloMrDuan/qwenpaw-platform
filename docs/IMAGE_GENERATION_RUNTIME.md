# Image Generation Runtime

> Phase: 17.5
>
> Status: offline implementation complete; real QwenPaw tenant and SenseNova API validation pending

## 1. Runtime boundary

Image generation is an atomic remote Tool capability, not an image-processing
Skill and not a second Agent Runtime.

```text
User: "生成一张……"
  -> QwenPaw Agent Tool selection
  -> PluginApi.register_tool("image_generation")
  -> core.image_generation.ImageGenerationService
  -> selected ImageGenerationProvider
  -> SenseNova remote API
  -> validated local PNG/JPEG
  -> core.contracts.Artifact
  -> QwenPaw ToolChunk/DataBlock when running inside QwenPaw
```

No module imports Hermes, starts a historical Bridge/Gateway, or installs a
local image model.

## 2. Provider-neutral contracts

`core/image_generation/` defines:

- `ImageGenerationRequest`: prompt, negative prompt, width, height, seed,
  model override, and count;
- `ImageGenerationResponse`: status, images, provider, model, seed, duration,
  error, error code, and optional task ID;
- `ImageGenerationProvider.generate(...)`: replaceable provider boundary;
- `ImageGenerationProviderRegistry`: explicit provider discovery;
- `ImageGenerationService`: progress capture and Artifact conversion.

The Tool layer depends on this contract rather than a SenseNova-specific
function. Future providers can implement the same interface without changing
the QwenPaw Tool name or processing Skills.

## 3. Status model

| Status | Meaning |
| --- | --- |
| `SUBMITTED` | Request is being submitted |
| `RUNNING` | Provider task or output materialization is in progress |
| `SUCCESS` | At least one validated local image and Artifact exist |
| `FAILED` | Provider, auth, response, download, or image validation failed |
| `TIMEOUT` | Bounded task polling exceeded its timeout |
| `PROVIDER_NOT_CONFIGURED` | Required remote Provider credential/registration is absent |

Missing `SENSENOVA_API_KEY` never returns `MODEL_RUNTIME_REQUIRED`, because
SenseNova is a remote Provider rather than a local model Runtime.

## 4. QwenPaw Tool registration

`plugins/sensenova-image-generation-tool/` is an official `type=tool` Plugin.
Its `register(api)` method calls:

```python
api.register_tool(
    tool_name="image_generation",
    tool_func=image_generation,
    description=...,
    icon="🎨",
    enabled=False,
)
```

The Tool is disabled by default until configuration is injected. The manifest
declares per-agent Tool configuration fields. The Runtime wrapper also accepts
the environment variables below, so no Secret is checked into Git.

The self-contained release ZIP bundles `core/image_generation` and the existing
Artifact contracts. Source-tree imports are not required after installation.

## 5. Routing boundary

The registered Tool description and offline boundary tests reserve explicit
new-image intent for `image_generation`:

| Request | Capability |
| --- | --- |
| 生成一张赛博朋克城市 | `image_generation` |
| 把这张图片压缩 | `image-toolkit` |
| 修复这张老照片 | `photo-restoration` |
| 把背景去掉 | `image-background-tools` |
| 把这张图放大2倍 | `image-quality-enhancer` |

An existing input image prevents the text-to-image fallback route. Real cloud
LLM Tool selection still requires installation/enabling acceptance in the
target QwenPaw tenant; offline tests do not impersonate that Agent decision.

## 6. Artifact rules

Provider URLs or base64 data are never returned as the final user result. The
Provider downloads/decodes the payload, validates it completely with Pillow,
atomically saves PNG/JPEG, and the Service creates one Artifact per image with:

- MIME type and filename;
- `artifact://` URI and local path metadata;
- SHA-256 checksum and byte size;
- width and height;
- provider, model, and seed provenance.

The QwenPaw wrapper converts successful image paths to `DataBlock` objects with
`file://` sources, matching the official Tool Plugin pattern.

## 7. Progress boundary

The Service records `SUBMITTED`, `RUNNING`, and `SUCCESS` progress messages.
The current official `PluginApi.register_tool` contract does not expose a
documented progress callback, so the Plugin returns a final explicit status and
does not claim cloud streaming. A future QwenPaw-supported progress API can map
the existing provider callback without changing provider logic.

## 8. Security and operations

- TLS verification remains enabled in the standard transport.
- Authentication uses a Bearer header and is never logged or returned.
- Retries are bounded and limited to transport/429/5xx failures.
- Polling has a positive interval and a hard timeout.
- Provider URLs must return a decodable PNG/JPEG before success.
- No `.env`, credential, generated file, cache, or local model is packaged.

Official QwenPaw Plugin reference:
[QwenPaw Plugin System](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md).
