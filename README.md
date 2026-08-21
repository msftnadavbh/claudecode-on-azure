# Claude Code + APIM + Microsoft Foundry

Deployable reference for 500+ developers using the native Anthropic Messages API:

`Claude Code -> Azure API Management -> Microsoft Foundry -> customer-managed Claude deployments`

APIM validates each developer's Entra identity, applies per-user fairness controls, removes caller credentials, and authenticates to Foundry with its managed identity. Production uses no shared gateway key and gives developers no APIM management-plane access.

## Implemented

- Generic Claude Code gateway mode with a refreshable Entra `apiKeyHelper`, no extra bearer-token cache, subprocess credential scrubbing, and independent Opus/Sonnet/Haiku deployment aliases.
- `/v1/messages` and `/v1/messages/count_tokens`, native headers/query passthrough, unbuffered SSE, credential stripping, and APIM backend circuit breaking without automatic POST retries.
- Basic v2 PoC and a fixed-capacity, single-region Premium v2 production baseline; autoscale is optional.
- Optional second APIM and public Traffic Manager failover, Premium v2 zone redundancy, and public/private networking profiles.
- Documented minimum `Foundry User` assignment on existing Foundry accounts; this repository does not manage Foundry accounts or deployments.
- Shared Log Analytics and workspace-based Application Insights, zero-body APIM diagnostics, low-cardinality metrics/alerts, and safe identity traces.
- OIDC validation/what-if/deployment/smoke workflows and asynchronous 500–2,500 stream tooling.

## PoC quick start

`infra/params/poc.bicepparam` deliberately uses fake identity/resource values and tiny `20 / 40 / 4000` limits. Override the fake values at deployment; do not reuse this profile for production.

```bash
scripts/test/validate.sh
az deployment group create --resource-group <rg> --template-file infra/main.bicep \
  --parameters infra/params/poc.bicepparam \
  --parameters entraTenantId=<tenant-guid> expectedAudience=api://<gateway-app-id> \
  foundryResourceGroupName=<foundry-rg> foundryAccountName=<foundry-account> \
  foundryBaseUrl=https://<resource>.services.ai.azure.com/anthropic \
  opusDeploymentName=<pinned-deployment> sonnetDeploymentName=<pinned-deployment> \
  haikuDeploymentName=<pinned-deployment>
```

## Production reference deployment

1. Create the caller-facing Entra application, app role, and GitHub OIDC federated identities.
2. Create/pin customer-owned Claude deployments and approve quotas.
3. Configure the GitHub `prod-primary` environment variables used by `infra/params/prod.bicepparam`; configure required reviewers.
4. Choose `public` or `private`. Private mode requires one dedicated Premium v2 VNet-injection subnet per APIM region and customer-managed DNS.
5. Record measured capacity values, dispatch `deploy`, review what-if, approve, deploy, and inspect the smoke result.
6. Distribute managed Claude Code settings from [docs/client-authentication.md](docs/client-authentication.md).

Production deliberately has no deployable defaults for tenant, Foundry, models, regions, capacity, networking, or alerts. See [docs/production-readiness.md](docs/production-readiness.md).

## Validation and load test

Validation requires Bash, ShellCheck, Python 3.11+, and Bicep CLI (or Azure CLI with Bicep).

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
- [Capacity](docs/03-capacity-plan.md)
- [Availability and DR](docs/availability-dr.md)
- [Networking](docs/networking.md)
- [Observability](docs/observability.md)
- [Load testing](docs/load-testing.md)
- [Operations and rollback](docs/operations-runbook.md)
- [Production readiness](docs/production-readiness.md)
- [Complexity reduction plan](docs/complexity-reduction-plan.md)
