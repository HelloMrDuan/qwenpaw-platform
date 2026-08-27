# image-background-tools

Remove, replace, blur, or crop the background of at least one existing input image, with optional segmentation Runtime. Never use for text-to-image or generating a new image from a prompt.

The source launcher uses the repository's canonical productivity runtime. The release builder vendors the required runtime into each standalone ZIP.

Phase 17.1 wires the `RembgAdapter` for `segment` and `alpha_matting`. The
default model is `u2netp`; configure the shared cache with
`QWENPAW_REMBG_MODEL_DIR`. Model weights remain outside the Skill ZIP.
