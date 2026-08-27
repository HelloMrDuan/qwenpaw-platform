# SenseNova Image Generation Tool

Official QwenPaw `type=tool` Plugin for generating a new image from a text
prompt through the remote SenseNova API. It registers `image_generation` with
`PluginApi.register_tool`; it is not an image-processing Skill and does not
start or import Hermes.

Configure the Tool in QwenPaw Console or inject these environment variables:

- `SENSENOVA_API_KEY` (required)
- `SENSENOVA_BASE_URL` (default `https://token.sensenova.cn/v1`)
- `SENSENOVA_IMAGE_MODEL` (default `sensenova-u1-fast`)

Historical aliases `SN_IMAGE_GEN_*` and `SN_*` remain supported for migration.
No credential value belongs in this directory or in a release archive.

## Size contract

The Tool accepts `image_size` (`1k` or `2k`) and a supported
`aspect_ratio`; the default is `2k` / `16:9`. It never asks the Agent to guess
SenseNova pixel buckets. An optional `requested_size` such as `1920x1080`
means the final output size: the provider receives the nearest supported native
bucket and the bundled image-toolkit performs a deterministic fit. Set
`require_native_size=true` to reject a non-native exact size without calling
the provider. The Console-configurable `default_fit_mode` is `cover`; `contain`
preserves the whole frame with padding, while `stretch` is explicit opt-in.

Successful QwenPaw responses contain the generated image as a `DataBlock` plus
a terminal `ToolChunk(SUCCESS)` JSON summary. Tool-call and user-turn IDs feed
a checksum-verified idempotency cache, preventing repeated paid calls for the
same request while allowing retryable failures to run again.

The checked-in source Plugin uses `core/image_generation`. A release package
must bundle that package, `core/contracts`, and the image-toolkit runtime so
installation does not depend on the qwenpaw-platform repository root.
