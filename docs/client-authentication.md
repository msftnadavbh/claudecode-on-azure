# Client authentication

## Decision

Use generic gateway mode. APIM exposes the native Anthropic protocol while Foundry is an internal backend. This keeps backend credentials and provider choice out of clients and provides documented `apiKeyHelper` refresh.

```bash
export APIM_BASE_URL=https://claude.example.com/claude
export APIM_AUDIENCE=api://<gateway-application-id>
export ANTHROPIC_DEFAULT_OPUS_MODEL=<pinned-opus-deployment>
export ANTHROPIC_DEFAULT_SONNET_MODEL=<pinned-sonnet-deployment>
export ANTHROPIC_DEFAULT_HAIKU_MODEL=<pinned-haiku-deployment>
eval "$(scripts/auth/print-claude-env.sh prod)"
```

Configure `apiKeyHelper` in centrally managed Claude Code settings with the helper's absolute path.

The helper prints only the raw Entra token. Claude Code uses helper output in both `Authorization: Bearer` and `x-api-key`; APIM validates `Authorization` and strips both headers before installing its own managed-identity authorization. Do not add a bearer prefix in the helper.

## Refresh behavior

Claude Code caches helper output for `CLAUDE_CODE_API_KEY_HELPER_TTL_MS` (five minutes here), much less than an Entra access-token lifetime. On expiry it invokes the helper again. The helper calls `az account get-access-token`; Azure CLI/MSAL silently refreshes its credential and the helper persists nothing.

The unit test invokes a mocked Azure CLI twice, proves fresh values are returned, and checks no token cache is created. A release gate must also keep one real Claude Code session open beyond one tenant token lifetime and issue another deterministic request. That live test requires the customer's tenant, Claude Code binary, and Conditional Access policy and was not executed in this sandbox.

If Azure CLI has no usable session, the helper exits nonzero and Claude Code cannot call APIM. Reauthenticate with the approved corporate flow; never substitute a static key.

Reference: [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect).
