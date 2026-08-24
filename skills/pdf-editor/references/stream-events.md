# PDF Editor progress event contract

Enable with `PDF_EDITOR_PROGRESS=1`.

Events are JSONL on stderr.

- `tool.start`
- `tool.progress`
- `file.created`
- `tool.result`
- `tool.error`

Recommended mapping into the global QwenPaw SSE event bus:

- `tool.start` -> `tool.start`
- `tool.progress` -> `tool.progress`
- `file.created` -> `file.created`
- `tool.result` -> `tool.result`
- `tool.error` -> `tool.error`

The final command result remains one JSON object on stdout. `executor/main.py` converts these engine events into full `core.contracts.StreamEvent` envelopes; the engine does not implement Runtime SSE.
