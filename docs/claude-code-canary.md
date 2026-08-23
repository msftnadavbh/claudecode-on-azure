# Claude Code live canary

This is a protected, manual gateway check. It uses the currently managed Claude Code gateway environment and settings; it never configures credentials or sources environment files.

```bash
python3 scripts/test/claude_code_canary.py
```

The script requires the managed gateway variables already present in its environment, runs the installed `claude` binary in a temporary Git repository, and emits only a small JSON result. It permits only Read, Edit, and Bash, explicitly disables `WebFetch` and `WebSearch`, sets a per-request budget of `$0.10`, and disables Claude Code session persistence. The temporary repository is deleted on exit; the current repository is not touched.

To exercise a later credential request in the same canary invocation, select a duration appropriate for the managed helper/cache policy. It intentionally has no default wait:

```bash
python3 scripts/test/claude_code_canary.py --refresh-after-seconds 360
```

Refresh mode makes a second deterministic read/test request after the wait. Run it only after the operator has authenticated with the approved Azure CLI flow; do not add a token, key, or environment-file sourcing to this command.
