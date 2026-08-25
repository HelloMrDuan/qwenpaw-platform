# QwenPaw Official Plugin Runtime Wrapper

This directory contains the reusable metadata and Runtime bridge used to adapt
the repository's internal Extension model to the official QwenPaw v2.1 Plugin
contract.

It provides:

- `manifest_template.py`: validates an internal `manifest.yaml` and produces an
  official `plugin.json` document;
- `plugin.template.json`: reviewable official Plugin template;
- `runtime.py`: binds an existing Adapter and `ExtensionRuntimeGateway`, forwards
  `MessageEvent`, delegates response conversion, and mirrors lifecycle state.

Official fields remain at the top level. Wrapper-specific `permissions`,
`config`, and required secret **names** are stored in the official free-form
`meta` object. Secret values are never generated or read.

The wrapper does not copy provider logic, start a recovered process, connect to
an API, or replace QwenPaw/AgentScope Runtime. A concrete official Plugin entry
must inject its existing Adapter, transport, lifecycle manager, and Gateway.
