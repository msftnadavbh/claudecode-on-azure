# Claude Code + APIM + Microsoft Foundry (Production Reference)

This repository is a production-aligned reference architecture for running Claude Code through Azure API Management (APIM) into Microsoft Foundry while preserving the native Anthropic Messages API contract.

## Core Architecture

Developer workstation
-> Claude Code
-> Azure API Management (enterprise gateway)
-> APIM authentication, authorization, quotas, telemetry, governance
-> Microsoft Foundry
-> Claude model deployments

## What This Repository Delivers

- Per-user runtime identity using Microsoft Entra tokens (no shared APIM subscription secret in production profile).
- APIM policy model that validates caller token, derives stable caller identity, applies per-user controls, removes caller auth before backend call, and authenticates to Foundry with APIM-managed identity.
- Separate `poc` and `prod` profiles with intentionally tiny PoC limits preserved and production parameters externalized.
- IaC structure for APIM-centric deployment and policy configuration.
- Synthetic SSE backend and gateway-load tools to test APIM stream concurrency independent from model quota.
- GitHub Actions OIDC deployment workflow skeleton with minimal permissions.

## Repository Layout

- `infra/`: Bicep entrypoint, modules, and profile parameter files.
- `apim/policies/`: APIM policy definitions for user auth, quota/rate limits, and backend auth handling.
- `scripts/auth/`: Token helper and Claude Code env bootstrap scripts.
- `scripts/test/`: Synthetic SSE backend and concurrency/load probe scripts.
- `docs/`: Architecture, constraints, migration plan, capacity model, and operations guidance.
- `.github/workflows/`: OIDC deployment workflow template.

## Quick Start

1. Read [docs/01-architecture.md](docs/01-architecture.md) and [docs/02-platform-constraints.md](docs/02-platform-constraints.md).
2. Set profile environment variables using `scripts/auth/print-claude-env.sh`.
3. Configure Claude Code with `apiKeyHelper` pointing to `scripts/auth/apim-user-token-helper.sh`.
4. Deploy infra using `infra/main.bicep` and either `infra/params/poc.bicepparam` or `infra/params/prod.bicepparam`.
5. Validate policy and scripting via `scripts/test/validate.sh`.
6. Run synthetic SSE capacity tests before any end-to-end Foundry throughput tests.

## Important Notes

- Production developers require no APIM management-plane secret access.
- APIM remains the enterprise gateway and always performs backend auth independently.
- TLS backend certificate validation remains enabled.
- Prompt/completion payloads are excluded from standard telemetry in the policy design.

## Production Deployment Inputs

`infra/params/prod.bicepparam` has no deployable defaults. Set the environment-specific APIM, identity, Foundry endpoint, and capacity variables listed in that file. Capacity limits must come from the approved record in [docs/03-capacity-plan.md](docs/03-capacity-plan.md); the deployment fails when they are absent or invalid.

The `FOUNDRY_BASE_URL` value is the Anthropic base URL copied from Foundry, including `/anthropic`, not a hostname inferred from a resource name.
