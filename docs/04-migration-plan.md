# Migration and File-by-File Implementation Plan

## Migration Approach

1. Stand up APIM production path in parallel with PoC path.
2. Introduce user-token validation and APIM-managed backend auth.
3. Move developers from static shared key to `apiKeyHelper` short-lived tokens.
4. Run synthetic SSE capacity tests before model quota expansion.
5. Gradually roll teams while monitoring APIM and Foundry quotas.

## File-by-File Change Scope

- `infra/main.bicep`: top-level deployment orchestration.
- `infra/modules/apim.bicep`: APIM service and named value profile configuration.
- `infra/params/poc.bicepparam`: tiny PoC profile.
- `infra/params/prod.bicepparam`: production profile placeholders.
- `apim/policies/claude-messages.xml`: authn/authz/quota/telemetry/backend auth policy.
- `scripts/auth/apim-user-token-helper.sh`: short-lived token helper for Claude Code.
- `scripts/auth/print-claude-env.sh`: profile-specific Claude env output.
- `scripts/test/synthetic_sse_backend.py`: synthetic backend.
- `scripts/test/sse_concurrency_probe.py`: concurrent stream probe.
- `scripts/test/validate.sh`: targeted validation automation.
- `.github/workflows/deploy.yml`: OIDC deployment skeleton.

## Validation Plan

- Script linting (`bash -n`).
- Python syntax validation (`python -m py_compile`).
- Policy guard checks for required security policy elements.
- Manual smoke test against synthetic backend.

## Open Decisions

- Regional active-active design and APIM SKU selection.
- Authoritative user authorization model (roles, groups, external entitlement API).
- Final Foundry deployment names, model versions, and quota allocations.
