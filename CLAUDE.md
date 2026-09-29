# Claude Code Runtime Guidance

Claude Code is the primary supported client baseline. This repository uses generic Anthropic gateway mode because APIM, not the client, owns Foundry authentication. Claude Desktop is an optional preview only.

## Managed production settings

Set centrally:

- `ANTHROPIC_BASE_URL=https://<enterprise-dns>/claude`
- `CLAUDE_CODE_API_KEY_HELPER_TTL_MS=300000`
- `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`
- `ANTHROPIC_DEFAULT_OPUS_MODEL=<pinned-foundry-deployment>`
- `ANTHROPIC_DEFAULT_SONNET_MODEL=<pinned-foundry-deployment>`
- `ANTHROPIC_DEFAULT_HAIKU_MODEL=<pinned-foundry-deployment>`
- `apiKeyHelper=<installed absolute path to apim-user-token-helper.sh>` on macOS/Linux/WSL, or the bundled `.windows.cmd` beside its `.windows.ps1` on native Windows

Managed settings include `APIM_AUDIENCE` and `APIM_TENANT_ID` (the caller tenant's canonical UUID), but do not populate the parent shell. Standalone helpers, smoke tools, and canaries need these values in their launch environment; the actual Claude helper child must receive them too. Roll out settings before the tenant-required helper and verify inheritance on pinned OS/client pilots with scrubbing enabled. If inheritance fails, stop rollout; do not disable scrubbing or use fallback credentials. Do not set `CLAUDE_CODE_USE_FOUNDRY`, `ANTHROPIC_FOUNDRY_BASE_URL`, a static Anthropic key, or a shared APIM key.

The bundled helpers ask Azure CLI/MSAL noninteractively for a current token in the explicit caller tenant on every invocation and write only the raw token to stdout. Claude Code's helper TTL limits invocations; Azure CLI/MSAL owns refresh and secure cache state. No custom token cache or interactive login is added. Claude Code places helper output in both credential headers; APIM validates the standard bearer `Authorization` header and removes both caller headers before Foundry. Verify native Windows execution on Windows; Linux tests skip it.

Environment scrubbing reduces accidental disclosure to Bash, hooks, and stdio MCP children. It does not isolate processes from the same operating-system user; use managed endpoints and OS controls as the stronger boundary.
