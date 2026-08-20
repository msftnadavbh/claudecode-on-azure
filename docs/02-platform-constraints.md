# Verified Platform Constraints and Assumptions

Validated against current first-party guidance as of 2026-08-20, with implementation constrained to documented capabilities and conservative defaults.

## Claude Code / Foundry

- Foundry mode variables are supported for base URL and auth token delivery.
- `apiKeyHelper` is preferred for short-lived token refresh in long-running sessions.
- Do not assume a one-hour token exported once at shell startup is sufficient for long-lived agent work.

## APIM

- `validate-azure-ad-token`, `rate-limit-by-key`, `quota-by-key`, and managed-identity auth patterns are supported and used.
- The gateway requires the configured Entra app role (`ClaudeCode.User` in the PoC profile) in addition to token audience and object ID.
- Payload logging is explicitly controlled; request/response body capture is disabled in this baseline.
- Policy keys are derived from stable identity claims to support per-user attribution and revocation.

## Identity

- Public client flow with Authorization Code + PKCE is the preferred interactive auth model.
- Group claim overage must be handled outside fixed-size JWT group arrays when authorization requires group semantics.
- Developer runtime should only require data-plane audience token acquisition, not APIM management-plane role access.

## GitHub Actions

- OIDC workload federation is used for Azure deployment auth.
- Workflow permissions are set to minimum needed (`id-token: write`, `contents: read`).
- Deployment workflow is structured for environment protection and review gates.

## First-party references

- [Claude Code on Microsoft Foundry](https://code.claude.com/docs/en/microsoft-foundry)
- [Connect Claude Code to an LLM gateway](https://code.claude.com/docs/en/llm-gateway-connect)
- [APIM `validate-azure-ad-token`](https://learn.microsoft.com/azure/api-management/validate-azure-ad-token-policy)
- [APIM LLM token limit](https://learn.microsoft.com/azure/api-management/llm-token-limit-policy)
- [Foundry model endpoints](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/endpoints)

## Explicit Assumptions Requiring Customer Decision

- Exact Entra tenant and audience design.
- Required claim set for authorization policy (for example role claim vs group lookup strategy).
- APIM SKU/region topology and DR objectives.
- Foundry region/deployment topology and quota partition strategy.
