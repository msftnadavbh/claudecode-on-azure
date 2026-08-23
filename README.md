# Claude Code + APIM + Microsoft Foundry

Deployable reference for 500+ developers using the native Anthropic Messages API:

`Claude Code -> Azure API Management -> Microsoft Foundry -> customer-managed Claude deployments`

APIM validates each developer's Entra identity, applies per-user fairness controls, removes caller credentials, and authenticates to Foundry with its managed identity. Production uses no shared gateway key and gives developers no APIM management-plane access.

## Implemented

- Generic Claude Code gateway mode with a refreshable Entra `apiKeyHelper`, no extra bearer-token cache, subprocess credential scrubbing, and independent Opus/Sonnet/Haiku deployment aliases.
- Managed Claude Desktop configuration generation for Windows and macOS with native per-user Entra sign-in.
- Read-only Foundry account, deployment, and quota preflight for all three model roles.
- Observer-only primary, secondary, failover, and private-network smoke evidence from protected in-network runners.
- Cross-platform managed Claude Code settings generation and 90-day deployment evidence retention.
- `/v1/messages` and `/v1/messages/count_tokens`, native headers/query passthrough, unbuffered SSE, credential stripping, and APIM backend circuit breaking without automatic POST retries.
- Basic v2 PoC and a fixed-capacity, single-region Premium v2 production baseline; autoscale is optional.
- Optional second APIM and public Traffic Manager failover, Premium v2 zone redundancy, and public/private networking profiles.
- Documented minimum `Foundry User` assignment on existing Foundry accounts; this repository does not manage Foundry accounts or deployments.
- Shared Log Analytics and workspace-based Application Insights, zero-body APIM diagnostics, low-cardinality metrics/alerts, and safe identity traces.
- OIDC OpenTofu plan/apply/smoke workflows and asynchronous 500–2,500 stream tooling.
- Manual, real-client Claude Code gateway canary with a bounded disposable edit/test check and optional refresh wait.

## PoC quick start

`infra/tofu/poc.tfvars.example` is intentionally incomplete and cannot deploy. Supply environment-specific values through the protected deployment workflow; do not reuse PoC limits for production.

```bash
scripts/test/validate.sh
tofu -chdir=infra/tofu init -backend-config=... -lockfile=readonly
tofu -chdir=infra/tofu plan -var-file=<reviewed.tfvars.json>
```

## Production reference deployment

1. Create the caller-facing Entra application, app role, and GitHub OIDC federated identities.
2. Create/pin customer-owned Claude deployments and approve quotas.
3. Configure the protected GitHub environment and external Azure Blob state backend described in [OpenTofu adoption](docs/tofu-adoption.md).
4. Choose `public` or `private`. Private mode requires one dedicated Premium v2 VNet-injection subnet per APIM region and customer-managed DNS.
5. Import existing resources, require a no-change plan, then dispatch `deploy`, review the sanitized OpenTofu plan summary, approve, apply, and inspect smoke evidence.
6. Distribute managed Claude Code settings from [docs/client-authentication.md](docs/client-authentication.md).

Production deliberately has no deployable defaults for tenant, Foundry, models, regions, capacity, networking, or alerts. See [docs/production-readiness.md](docs/production-readiness.md).

## Validation and load test

Validation requires Bash, ShellCheck, Python 3.11+, OpenTofu 1.12.3, and Bicep CLI (temporarily, for rollback-reference compilation).

```bash
scripts/test/validate.sh
python3 scripts/test/synthetic_sse_backend.py
python3 scripts/test/sse_concurrency_probe.py \
  --url http://127.0.0.1:8088/v1/messages \
  --concurrency 500 --stream-duration 60
```

Direct Foundry load targets require `--allow-live-model`; billable model load is never run by CI.

## Documentation

- [Architecture](docs/01-architecture.md)
- [Security](docs/security.md)
- [Client authentication](docs/client-authentication.md)
- [Claude Desktop](docs/desktop-deployment.md)
- [Foundry preflight](docs/foundry-preflight.md)
- [Claude Code managed settings](docs/claude-code-managed-settings.md)
- [Claude Code live canary](docs/claude-code-canary.md)
- [Capacity](docs/03-capacity-plan.md)
- [Availability and DR](docs/availability-dr.md)
- [Networking](docs/networking.md)
- [Observability](docs/observability.md)
- [Load testing](docs/load-testing.md)
- [Operations and rollback](docs/operations-runbook.md)
- [Production readiness](docs/production-readiness.md)
- [Complexity reduction plan](docs/complexity-reduction-plan.md)
