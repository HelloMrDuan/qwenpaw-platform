# image-background-tools

Safe solid-background removal, replacement, blur and subject crop with optional segmentation Runtime.

The source launcher uses the repository's canonical productivity runtime. The release builder vendors the required runtime into each standalone ZIP.

Phase 17.1 wires the `RembgAdapter` for `segment` and `alpha_matting`. The
default model is `u2netp`; configure the shared cache with
`QWENPAW_REMBG_MODEL_DIR`. Model weights remain outside the Skill ZIP.
