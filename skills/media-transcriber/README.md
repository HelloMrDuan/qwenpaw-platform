# media-transcriber

Media inspection/audio extraction plus ASR transcript and meeting-report orchestration.

The source launcher uses the repository's canonical productivity runtime. The release builder vendors the required runtime into each standalone ZIP.

Phase 17.1 wires the `FasterWhisperAdapter`. Configure a local model with
`QWENPAW_ASR_MODEL_PATH`, or select `tiny`, `base` or `small` with
`QWENPAW_ASR_MODEL`. Model weights remain under `.runtime/models/asr` and are
never included in this Skill ZIP.
