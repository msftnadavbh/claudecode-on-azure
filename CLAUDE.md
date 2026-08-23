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
- `apiKeyHelper=<absolute-path>/scripts/auth/apim-user-token-helper.sh`

Set `APIM_AUDIENCE` in the launch environment. Do not set `CLAUDE_CODE_USE_FOUNDRY`, `ANTHROPIC_FOUNDRY_BASE_URL`, a static Anthropic key, or a shared APIM key.

The helper asks Azure CLI/MSAL for a current user token on every helper invocation and writes only the raw token to stdout. Claude Code's helper TTL limits invocations; Azure CLI/MSAL owns refresh and secure cache state. Claude Code places helper output in both credential headers; APIM validates the standard bearer `Authorization` header and removes both caller headers before Foundry.

Environment scrubbing reduces accidental disclosure to Bash, hooks, and stdio MCP children. It does not isolate processes from the same operating-system user; use managed endpoints and OS controls as the stronger boundary.
