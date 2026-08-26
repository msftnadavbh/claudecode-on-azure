# Claude Code Enterprise Gateway on Azure

Deploy a governed Claude Code gateway that authenticates callers with Microsoft Entra, applies controls in Azure API Management (APIM), and calls Microsoft Foundry Claude deployments with APIM's managed identity. Configure and operate managed clients through the native Anthropic Messages API without direct Foundry credentials.

## What this deploys

- `/claude` on APIM, with native `/v1/messages` and `/v1/messages/count_tokens`, unbuffered SSE, and APIM-local unauthenticated `/health`.
- A fixed-capacity, public, single-region `StandardV2` APIM baseline. Use `PremiumV2` only for zone redundancy or private VNet injection.
- Optional second APIM and public Traffic Manager. You provide private DNS, failover, custom DNS, and certificates.
- APIM policy, managed identity access to Foundry, optional telemetry and alerts, and managed Claude Code configuration generators. In `greenfield` mode it also creates a new resource group, one AIServices Foundry account, one project, and one Claude deployment.

![Conceptual Claude Code Enterprise Gateway on Azure architecture. The written implementation boundary below is authoritative.](assets/architecture/claude-code-enterprise-gateway.png)

`Claude Code → Microsoft Entra ID → Azure API Management → Microsoft Foundry → your Claude deployments`

## Before you begin

Choose one immutable state mode. `existing` (default) adopts your existing resource group and cross-subscription Foundry account with three deployment names. `greenfield` creates a new target-subscription resource group, AIServices/S0 Foundry account, project, and exactly one public Claude deployment; that deployment is mapped to the Opus, Sonnet, and Haiku roles. Use a new Blob state key for greenfield and never switch mode for an existing state.

You still provide external Blob state/container, Entra caller app/roles/consent, GitHub identities/environments/OIDC, VNet/DNS/certificates/private endpoints, Action Group, and a native Windows helper. Greenfield is public-only, creates no Entra/GitHub/state/network resources, and its Marketplace checkbox authorizes OpenTofu/modelProviderData to accept Anthropic Marketplace terms and incur billing. See [getting started](docs/getting-started.md) and the [GitHub configuration inventory](docs/github-configuration.md).

## Deploy

1. Configure [GitHub environments, OIDC, state, secrets, and variables](docs/github-configuration.md).
2. Run the read-only [Foundry preflight](docs/foundry-preflight.md) and repository validation.
3. Dispatch the protected `deploy` workflow with matching `environment_profile` and `networking_profile`.
4. Retain public smoke evidence, or run protected in-network `ha-smoke` for private or HA deployments.

OpenTofu is the only active deployment path: OpenTofu `1.12.3`, AzureRM `4.56.0`, and AzAPI `2.12.0`. Existing-mode Foundry deployment names are allowlisted; a secondary Foundry account must expose the same names.

## Configure Claude Code

Use the bundled helper on macOS, Linux, and WSL; provide and pilot a native Windows helper before a Windows rollout. [Configure managed Claude Code settings](docs/claude-code-managed-settings.md) and run the [client canary](docs/claude-code-canary.md). Claude Desktop is an optional preview.

## Validate

Requires Bash, Python 3, ShellCheck, and OpenTofu.

```bash
scripts/test/validate.sh
```

This checks repository configuration and local tools. It does not prove Foundry quota, APIM capacity, private connectivity, SLOs, failover, or client-fleet behavior; use the [production readiness gates](docs/production-readiness.md) before rollout.

## Documentation

- [Documentation](docs/index.md)
- [Architecture](docs/01-architecture.md)
- [Networking and availability](docs/networking.md) and [operations](docs/operations-runbook.md)
- [Troubleshooting](docs/troubleshooting.md)
