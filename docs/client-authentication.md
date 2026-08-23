# Client authentication

## Decision

Use generic gateway mode. APIM exposes the native Anthropic protocol while Foundry is an internal backend. This keeps backend credentials and provider choice out of clients and provides documented `apiKeyHelper` refresh.

Generate and deploy platform-specific managed files with [Claude Code managed settings](claude-code-managed-settings.md). This generator is the sole production Claude Code client-configuration path; device management owns installation and rollback. Do not use shell profiles or per-user environment setup.

The helper prints only the raw Entra token. Claude Code uses helper output in both `Authorization: Bearer` and `x-api-key`; APIM validates `Authorization` and strips both headers before installing its own managed-identity authorization. Do not add a bearer prefix in the helper.

## Refresh behavior

Claude Code caches helper output for `CLAUDE_CODE_API_KEY_HELPER_TTL_MS` (five minutes here), much less than an Entra access-token lifetime. On expiry it invokes the helper again. The helper calls `az account get-access-token`; Azure CLI/MSAL silently refreshes its credential and the helper persists nothing.

The unit test invokes a mocked Azure CLI twice, proves fresh values are returned, and checks no token cache is created. Use the manual [real-client canary](claude-code-canary.md) with an operator-selected wait to make a second deterministic request after the desired refresh interval. That live test requires the customer's tenant, Claude Code binary, and Conditional Access policy and was not executed in this sandbox.

If Azure CLI has no usable session, the helper exits nonzero and Claude Code cannot call APIM. Reauthenticate with the approved corporate flow; never substitute a static key.

Reference: [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect).
