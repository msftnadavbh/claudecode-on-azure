# Verified platform constraints

Verified against first-party documentation on 2026-08-20:

- Generic gateway mode uses `ANTHROPIC_BASE_URL`; `apiKeyHelper` supplies the dynamic gateway credential.
- `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` strips Anthropic/cloud credentials from child environments but is not host-process isolation.
- Foundry deployment names, not marketing model aliases, are configured for Opus/Sonnet/Haiku.
- Current Foundry data-plane authentication documentation uses `https://cognitiveservices.azure.com`. The preliminary issue suggestion of `https://ai.azure.com` was not supported by the current authentication documentation.
- Anthropic support in APIM LLM policies requires a v2 tier, so PoC uses Basic v2.
- `buffer-response="false"` is required for SSE; body logging stays at zero bytes.
- Premium v2 is deployed as separate regional services because it does not provide classic Premium geo-replication.
- Backend circuit breaking can propagate overload but must not blindly replay streaming POSTs.
- Global Standard and Data Zone quota scopes differ; additional resources do not imply additional effective quota.

References:

- [Claude Code on Microsoft Foundry](https://code.claude.com/docs/en/microsoft-foundry)
- [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect)
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars)
- [Foundry authentication and authorization](https://learn.microsoft.com/azure/foundry/concepts/authentication-authorization-foundry)
- [APIM LLM token limit](https://learn.microsoft.com/azure/api-management/llm-token-limit-policy)
- [APIM v2 tiers](https://learn.microsoft.com/azure/api-management/v2-service-tiers-overview)
- [APIM backends](https://learn.microsoft.com/azure/api-management/backends)
- [APIM SSE](https://learn.microsoft.com/azure/api-management/how-to-server-sent-events)
