# WeCom Runtime Adapter Reference

> Status: `LEGACY / FALLBACK / REFERENCE ONLY`.

QwenPaw v2.1.0 provides the production-default built-in 企业微信 Channel,
including Bot ID/Secret configuration, QR-code authorization, media directory,
and group-chat context. This Adapter remains only for offline contract tests,
historical Bridge analysis, and disaster-recovery reference.

Do not:

- implement a WeCom `BaseChannel` here;
- add custom WeCom Channel registration;
- deploy this Adapter as a replacement for the built-in Channel;
- modify or start the recovered Node Bridge as part of normal production setup.

The existing `runtime.py`, tests, manifests, and recovered sources remain
unchanged and must not be deleted. See `docs/QWENPAW_CHANNEL_STRATEGY.md`.
