# Telegram Extension Channel Plugin

> Status: `LEGACY / FALLBACK / REFERENCE ONLY`. Production uses the QwenPaw
> v2.1.0 built-in Telegram Channel. Do not add a custom Telegram `BaseChannel`
> or `register_channel()` implementation here.

Historical QwenPaw Plugin packaging facade for the repository's recovered
Telegram Extension Adapter. It remains for forensic, fallback, and regression
reference only.

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

Phase 12.6 used `scripts/build_extension.py --qwenpaw-plugin
telegram-channel-plugin` to validate self-contained packaging. That result is
historical evidence, not a production recommendation. Custom Telegram Channel
registration work is closed; configure and validate the built-in Channel.
