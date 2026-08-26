# Documentation index

This is the customer documentation landing page for validating and operating this reference implementation.

## Implementation boundary

| Repository-managed | Customer-owned |
| --- | --- |
| APIM APIs and policies, APIM managed identities, `Foundry User` role assignments, optional telemetry/alerts, optional Traffic Manager, and managed-client configuration generators | Foundry accounts and model deployments; Entra app registrations; GitHub identities/environments; Blob state; resource group; subnets, DNS, certificates, and Foundry private endpoints; incident routing; client deployment; and a native Windows helper |

The active deployment path is OpenTofu only. It creates no custom enterprise gateway hostname. `/claude/health` is APIM-local and does not test Foundry. The `migration/bicep` material is deprecated and non-authoritative; do not use it for deployment.

## Choose your path

| Role or stage | Read next |
| --- | --- |
| Platform owner choosing public, private, or HA topology | [Getting started](getting-started.md), [Architecture](01-architecture.md), [Networking](networking.md), [Availability and DR](availability-dr.md) |
| GitHub/Azure deployment administrator | [GitHub configuration](github-configuration.md), [Foundry preflight](foundry-preflight.md), [OpenTofu adoption](../migration/tofu/tofu-adoption.md) |
| Security and identity owner | [Security](security.md), [Client authentication](client-authentication.md) |
| Capacity and operations owner | [Capacity and load](03-capacity-plan.md), [Load testing](load-testing.md), [Observability](observability.md), [Operations and rollback](operations-runbook.md) |
| Endpoint-management owner | [Managed Claude Code settings](claude-code-managed-settings.md), [Client canary](claude-code-canary.md), [Desktop preview](desktop-deployment.md) |
| Release approver | [Production readiness](production-readiness.md), [Troubleshooting](troubleshooting.md) |

## Reference material

- [Platform constraints](02-platform-constraints.md) records the relevant service constraints.
- [Migration and adoption](04-migration-plan.md) distinguishes a new gateway from existing-resource adoption.
