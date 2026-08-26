# Claude Code Enterprise Gateway on Azure

Deploy a governed Claude Code gateway for customer validation: Microsoft Entra authenticates callers, Azure API Management (APIM) applies gateway controls, and APIM's managed identity calls customer-owned Microsoft Foundry Claude deployments. Clients use the native Anthropic Messages API without direct Foundry credentials.

For platform and security teams validating a managed Claude Code rollout—not a claim that a particular topology, capacity, or fleet size is already proven in production.

## What this deploys

- `/claude` on APIM, with native `/v1/messages` and `/v1/messages/count_tokens`, unbuffered SSE, and APIM-local unauthenticated `/health`.
- A fixed-capacity, public, single-region `StandardV2` APIM baseline. Use `PremiumV2` only for zone redundancy or private VNet injection.
- Optional second APIM and public Traffic Manager. Private DNS, failover, custom DNS, and certificates remain customer-owned.
- APIM policy, managed identity access to Foundry, optional telemetry and alerts, and managed Claude Code configuration generators.

![Conceptual Claude Code Enterprise Gateway on Azure architecture. The written implementation boundary below is authoritative.](assets/architecture/claude-code-enterprise-gateway.png)

`Claude Code → Microsoft Entra ID → Azure API Management → Microsoft Foundry → customer-managed Claude deployments`

## Customer prerequisites

Before deployment, provide the customer-owned resources and decisions: Foundry account and three pinned deployment names; Entra app registration and assignments; GitHub identities, protected environments, and OIDC federation; a resource group and external Azure Blob state; and, where selected, subnets, DNS, certificates, Foundry private endpoints, telemetry destinations, and a native Windows helper. This repository does not create them.

## Supported baseline

OpenTofu is the only active deployment path: OpenTofu `1.12.3`, AzureRM `4.56.0`, and AzAPI `2.7.0`. Three configured Foundry deployment names are allowlisted by APIM; a secondary Foundry account, when used, must expose the same names. Claude Code is supported through the bundled helper on macOS, Linux, and WSL; native Windows requires a customer helper. Claude Desktop is an optional preview.

## Customer journey

1. Choose the [topology and prerequisites](docs/getting-started.md).
2. Configure [GitHub environments, OIDC, state, and inputs](docs/github-configuration.md).
3. Run [Foundry preflight](docs/foundry-preflight.md), validate, dispatch the protected workflow, and complete the applicable smoke test.
4. Pilot managed Claude Code clients, then approve capacity, operations, and release gates.

## Validation boundary

Repository validation checks configuration and local tools; it does not prove your Foundry quota, APIM capacity, private connectivity, SLOs, failover, or client fleet. The [production readiness gates](docs/production-readiness.md) define the customer evidence required before rollout.

## Documentation

Start at the [documentation index](docs/index.md) for lifecycle and role-based guidance. For operational symptoms, see [troubleshooting](docs/troubleshooting.md).

## Validate the repository

Requires Bash, Python 3, ShellCheck, and OpenTofu.

```bash
scripts/test/validate.sh
```
