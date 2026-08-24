# PDF Editor progress event contract

Enable with `PDF_EDITOR_PROGRESS=1`.

Events are JSONL on stderr.

- `tool.start`
- `tool.progress`
- `file.ready`
- `tool.result`
- `message.error`

Recommended mapping into the global QwenPaw SSE event bus:

- `tool.start` -> `tool.start`
- `tool.progress` -> `tool.progress`
- `file.ready` -> `file.ready`
- `tool.result` -> `tool.result`
- `message.error` -> `message.error`

The final command result remains one JSON object on stdout.
