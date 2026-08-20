# Claude Code Runtime Guidance

This repository assumes Claude Code is configured in Foundry mode and routed through APIM.

## Production Runtime

Set:

- `CLAUDE_CODE_USE_FOUNDRY=1`
- `ANTHROPIC_FOUNDRY_BASE_URL=https://<apim-host>/claude`
- `CLAUDE_CODE_API_KEY_HELPER_TTL_MS=300000`
- `apiKeyHelper=<absolute-path>/scripts/auth/apim-user-token-helper.sh`

Do not set a static shared APIM key for production users.

## PoC Runtime

PoC profile keeps intentionally tiny limits to demonstrate policy behavior. Use only in non-production environments.

## Security

- Caller token is validated at APIM.
- Caller token is not forwarded to Foundry.
- APIM managed identity obtains backend token for Foundry.
- Developers require no APIM management-plane permissions.
