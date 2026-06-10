# Langfuse Observability Plugin for Claude Code

  Trace every Claude Code session to [Langfuse](https://langfuse.com) — turns, generations, tool calls, and token usage — with zero code changes.

  ## Install
  
  ```bash
  claude plugin marketplace add langfuse/Claude-Observability-Plugin
  claude plugin install langfuse@langfuse-observability

  Restart Claude Code after install.

  On enable, you'll be prompted for:

  ┌─────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │        Field        │                                             Description                                              │
  ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ LANGFUSE_SECRET_KEY │ Your Langfuse secret key (sk-lf-...). Stored in your OS keychain.                                    │
  ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ LANGFUSE_PUBLIC_KEY │ Your Langfuse public key (pk-lf-...).                                                                │
  ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ LANGFUSE_BASE_URL   │ https://us.cloud.langfuse.com (default), https://cloud.langfuse.com for EU, or your self-hosted URL. │
  ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ CC_LANGFUSE_DEBUG   │ Verbose logging to ~/.claude/state/langfuse_hook.log.                                                │
  └─────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Get keys from your Langfuse project settings → API Keys.

  Requirements

  - Python 3.9+ available as python3
  - langfuse SDK 4.x: pip install "langfuse>=4.0,<5"

  If the SDK isn't importable, the hook exits silently — no impact on Claude Code.

  How it works

  A Stop hook reads the session transcript incrementally on every turn and emits a Langfuse trace with one span per turn, nested generations per assistant message, and child
  tool spans for every tool call. Token usage is captured when present.

  State is kept in ~/.claude/state/langfuse_state.json so re-runs only emit new turns.

  Reconfigure

  claude plugin disable langfuse
  claude plugin enable langfuse

  Uninstall

  claude plugin uninstall langfuse

  Troubleshooting

  - Nothing in Langfuse: check ~/.claude/state/langfuse_hook.log (enable CC_LANGFUSE_DEBUG).
  - Hook not firing: confirm with claude plugin list that langfuse is enabled; restart Claude Code.
  - langfuse import errors: ensure the python3 on your PATH has the SDK installed.

  License

  MIT
```

## Privacy

This plugin transmits your Claude Code session data — conversation turns, assistant
generations, tool calls, and token-usage statistics — to the Langfuse endpoint you
configure (`LANGFUSE_BASE_URL`, default `https://us.cloud.langfuse.com`; EU and
self-hosted endpoints are supported). Data is sent at the end of each session (the
`Stop` hook) using the Langfuse API keys you provide, which are stored in your OS
keychain. No data is sent anywhere other than the endpoint you configure.

For how Langfuse Cloud handles data it receives, see the Langfuse privacy policy:
https://langfuse.com/privacy . When using a self-hosted Langfuse instance, your data
stays within your own infrastructure.
