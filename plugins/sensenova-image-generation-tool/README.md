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

The checked-in source Plugin uses `core/image_generation`. A release package
must bundle that package and `core/contracts` so installation does not depend
on the qwenpaw-platform repository root.
