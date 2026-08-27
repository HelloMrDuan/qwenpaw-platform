# Runtime Model Discovery

## Goal

Runtime restart must not require temporary shell exports or repeat model
downloads. Phase 17.3 separates the standard workspace target from read-only
discovery sources and never embeds model files in a Skill ZIP.

## Faster Whisper priority

The `tiny`, `base` or `small` CTranslate2 model is selected in this order:

1. explicit `QWENPAW_ASR_MODEL_PATH`;
2. `<workspace>/.runtime/models/asr/`;
3. `QWENPAW_ASR_CACHE_DIR`;
4. HuggingFace standard caches from `HF_HUB_CACHE`,
   `HUGGINGFACE_HUB_CACHE`, `HF_HOME`, `XDG_CACHE_HOME`, or
   `Path.home()/.cache/huggingface/hub`;
5. download only when `QWENPAW_RUNTIME_ALLOW_MODEL_DOWNLOAD=1`.

HF repositories are matched by
`models--Systran--faster-whisper-<model>/snapshots/*`. A candidate snapshot must
contain both `model.bin` and `config.json`. No snapshot hash is hardcoded. When
an existing snapshot is found, its directory is passed directly to
`WhisperModel` with `local_files_only=True`.

## rembg priority

The default is `u2netp`. Discovery checks:

1. `<workspace>/.runtime/models/rembg/`;
2. the models root in `QWENPAW_REMBG_MODEL_DIR`;
3. `Path.home()/.rembg/models/`.

Both the real nested layout `<root>/u2netp/u2netp.onnx` and the legacy flat
layout `<root>/u2netp.onnx` are recognized. The environment variable points to
the models root, not to the `u2netp` child directory. `u2net`,
`isnet-general-use` and their matching nested filenames follow the same rule.

## Offline behavior

`QWENPAW_RUNTIME_ALLOW_MODEL_DOWNLOAD` defaults to `0`. Existing discovered
models remain usable with downloads disabled. Health states are:

- package + Adapter + model + minimal load/inference pass: `AVAILABLE`;
- package + Adapter but no model: `DEGRADED`;
- missing package: `MISSING`;
- model exists but load/inference fails: `RUNTIME_ERROR`.

The sample [.runtime/runtime.env.example](../.runtime/runtime.env.example) uses
only non-secret, portable values and contains no machine path.

## Inspect and normalize

Inspect without modifying files:

```bash
python scripts/normalize_runtime_models.py --inspect
```

The report includes Runtime, model, discovered source, workspace target, size,
and whether normalization is useful.

Optionally create directory symlinks:

```bash
python scripts/normalize_runtime_models.py --link
```

The command never copies model bytes and never replaces an existing target. If
symlinks are unsupported or permission is denied, it reports
`LINK_UNSUPPORTED`; the original cache remains untouched and is still available
through automatic discovery.
