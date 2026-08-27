# image-toolkit

Process at least one existing input image with deterministic Pillow inspection, conversion, geometry, metadata, batch, or duplicate operations. Never use for text-to-image or generating a new image from a prompt.

`fit` accepts `width`, `height`, and `fit_mode` (`cover`, `contain`, or
`stretch`). The image-generation provider adapter uses this deterministic
operation only after remote generation when an exact final pixel size was
requested.

The source launcher uses the repository's canonical productivity runtime. The release builder vendors the required runtime into each standalone ZIP.
