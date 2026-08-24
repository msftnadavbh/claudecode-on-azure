# Production Claude Code Gateway on Azure

**Secure Claude Opus 5 access for 500+ developers through Azure API Management and Microsoft Foundry.**

This production-grade reference implementation gives engineering teams one governed Claude Code endpoint without shared API keys or direct Foundry credentials. Microsoft Entra authenticates every developer, APIM enforces identity-aware controls, and its managed identity calls customer-owned Claude deployments through the native Anthropic Messages API.

`Claude Code -> Microsoft Entra ID -> Azure API Management -> Microsoft Foundry -> Claude Opus 5`

## Architecture

![Claude Code Enterprise Gateway on Azure](assets/architecture/claude-code-enterprise-gateway.png)

The production baseline is one fixed-capacity, single-region `StandardV2` APIM gateway. `PremiumV2` adds private VNet injection and zone redundancy; an optional second APIM and Traffic Manager provide regional failover.

## Why it is production grade

| Capability | Implementation |
| --- | --- |
| Identity | Short-lived Entra tokens, tenant/audience/app-role validation, and independent user revocation |
| Credential isolation | APIM strips caller credentials and uses its managed identity with least-privilege `Foundry User` access |
| Governance | Per-user RPM, token, and concurrent-stream controls plus an aggregate admission limit |
| Model routing | Independently pinned Opus, Sonnet, and Haiku deployment aliases, including customer-managed [`claude-opus-5`](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/claude-models) |
| Streaming | Native `/v1/messages` and `/v1/messages/count_tokens` passthrough with unbuffered SSE responses |
| Resilience | Backend circuit breaking without replaying inference POSTs; optional active/passive regional failover |
| Observability | Application Insights, Log Analytics, low-cardinality alerts, safe identity traces, and zero-body diagnostics |
| Delivery | OpenTofu, remote Azure Blob state, GitHub OIDC, reviewed plan/apply gates, smoke evidence, and rollback controls |
| Scale | Capacity model and synthetic SSE tooling for sustained 500–2,000 streams and controlled overload at 2,500 |

## Production deployment

1. Deploy and pin the required Claude models in Microsoft Foundry, including Opus 5, and approve the effective RPM/TPM quota.
2. Create the caller-facing Entra application, GitHub OIDC identities, protected environments, and external Azure Blob state backend.
3. Supply reviewed environment-specific inputs, import existing resources, and require a no-change adoption plan.
4. Run the protected `deploy` workflow, approve the sanitized plan, inspect smoke evidence, and distribute centrally managed Claude Code settings.

Start with the [production readiness gates](docs/production-readiness.md), [client authentication guide](docs/client-authentication.md), and [OpenTofu adoption runbook](migration/tofu/tofu-adoption.md).

## Validate

```bash
scripts/test/validate.sh

python3 scripts/test/synthetic_sse_backend.py
python3 scripts/test/sse_concurrency_probe.py \
  --url http://127.0.0.1:8088/v1/messages \
  --concurrency 500 \
  --stream-duration 60
```

Direct Foundry load tests are billable and require the explicit `--allow-live-model` flag.

> [!IMPORTANT]
> The repository implements the production controls; each deployment must still prove its own Opus 5 quota, APIM capacity, SLOs, alerting, failover, and rollback before a 500+ developer rollout. Foundry accounts, model deployments, production sizing, regions, and network topology remain customer-owned inputs.

## Documentation

- **Design:** [Architecture](docs/01-architecture.md) · [Security](docs/security.md) · [Capacity](docs/03-capacity-plan.md) · [Availability and DR](docs/availability-dr.md) · [Networking](docs/networking.md)
- **Operate:** [Observability](docs/observability.md) · [Load testing](docs/load-testing.md) · [Operations and rollback](docs/operations-runbook.md) · [Production readiness](docs/production-readiness.md)
- **Clients:** [Authentication](docs/client-authentication.md) · [Managed settings](docs/claude-code-managed-settings.md) · [Live canary](docs/claude-code-canary.md) · [Claude Desktop preview](docs/desktop-deployment.md)
- **Deploy:** [Foundry preflight](docs/foundry-preflight.md) · [OpenTofu adoption](migration/tofu/tofu-adoption.md)
