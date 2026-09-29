# Getting started

Use this checklist to deploy and validate the gateway. You need Azure subscription access, GitHub administration, and access to Foundry, Entra, networking, and endpoint management.

## 1. Choose topology

| Need | Select | You provide |
| --- | --- | --- |
| Default deployment | Public, one `StandardV2` APIM | Publish the default APIM URL or your DNS/certificate separately. |
| Private gateway or zone redundancy | `PremiumV2` | Provide dedicated subnet(s), private DNS/routing, and test from in-network runners. |
| Regional gateway continuity | Optional second APIM | Provide secondary region/name; optionally a same-named secondary Foundry deployment set. |
| Public priority routing | Second APIM plus Traffic Manager | Own the enterprise hostname and traffic-change procedure. |

## 2. Choose deployment mode and prepare prerequisites

- `existing` (default) uses your existing resource group and Foundry account, including three pinned deployment names; it continues to support cross-subscription Foundry.
- `greenfield` creates a **new** target-subscription resource group, AIServices/S0 Foundry account, project, and one Claude deployment. It is public-only, does not deploy a secondary Foundry account, and maps its one deployment to all three Claude Code roles. Its catalog preflight intentionally accepts only Anthropic models hosted on Azure. Supply exact model name, version, SKU (`GlobalStandard` or `DataZoneStandard`), positive capacity, project/location, and organization/country/industry attestation inputs. The Marketplace checkbox authorizes OpenTofu/modelProviderData to accept Anthropic Marketplace terms and incur billing; ensure billing and quota are approved.
- Use a new Blob state key for a new greenfield environment. The state sentinel blocks changing `deployment_mode` after the first apply. A retry after a partial greenfield apply accepts the named resource group only when its `azurerm_resource_group.greenfield[0]` address is already in that state; a fresh state still rejects an existing group.
- Create the Entra caller application, audience, app role, assignments, consent, and GitHub smoke identity.
- Create GitHub `poc` and protected `prod-primary` environments, OIDC federation, and versioned/soft-deleted external Blob state. In existing mode, also create the resource group.
- For private or HA deployments, prepare subnets, DNS, routing, certificates, private endpoints, and self-hosted smoke runners.

## 3. Configure and validate

Follow the exact [GitHub configuration inventory](github-configuration.md). Run the read-only [Foundry preflight](foundry-preflight.md), then run `scripts/test/validate.sh` from a workstation with Bash, Python 3, ShellCheck, and OpenTofu.

## 4. Deploy and smoke

Dispatch `deploy` with a matching `environment_profile` and `networking_profile`. Review the sanitized plan summary; deployment regenerates inputs and plan, compares their summaries, and rejects non-equivalent results. Public deployments run the existing smoke command with up to six attempts, 30 seconds apart. The retained artifact is the final attempt's safe matrix evidence, including infrastructure metadata; failures are retained when the process generates JSON. An empty evidence file means the final attempt produced no stdout; never reuse evidence from a prior attempt. Cancellation does not guarantee evidence. Private deployments require protected in-network `ha-smoke` evidence before release; operators own traffic changes.

Outputs include gateway URLs and role models in both modes. Greenfield additionally reports `deploymentMode`, `foundryResourceId`, `foundryBaseUrl`, `foundryProjectName`, and `managedFoundryDeploymentName`.

## 5. Pilot clients and prepare for rollout

Generate and deploy [managed Claude Code settings](claude-code-managed-settings.md), run a [client canary](claude-code-canary.md), and complete the [production readiness](production-readiness.md) gates. Size APIM and approve Foundry quota using measured evidence, not local synthetic results.
