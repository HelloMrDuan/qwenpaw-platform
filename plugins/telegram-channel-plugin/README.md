# Telegram Extension Channel Plugin

Official QwenPaw v2.1 Plugin facade for the repository's existing Telegram
Extension Adapter.

## Boundary

The Plugin entry imports and delegates to `adapters/telegram/runtime.py`. It does
not copy or modify `telegram_bridge.py`, `telegram_bridge_main.py`, token handling,
provider requests, or Hermes logic.

The entry performs four controlled operations:

1. load and validate the internal Telegram Extension Manifest;
2. bind the existing `TelegramRuntimeAdapter` to `ExtensionRuntimeGateway`;
3. forward normalized `MessageEvent` objects to an injected handler;
4. mirror approved local lifecycle actions and delegate outbound conversion.

## Current phase

Phase 12 validates the official `plugin.json` and the local wrapper contract
offline. It does not upload this directory, start the recovered Bridge, read a
Bot Token, or register a live Telegram Channel instance.

The `TELEGRAM_BOT_TOKEN` entry in `plugin.json` is a required secret **name** and
UI field declaration only. No value belongs in the archive.

Before a tenant upload, the release builder must assemble the wrapper and the
required `qwenpaw-platform` modules into one self-contained official Plugin ZIP,
then validate it against the exact QwenPaw tenant version.
