# Getting started

Use this checklist to deploy and validate the gateway. You need Azure subscription access, GitHub administration, and access to Foundry, Entra, networking, and endpoint management. This repository deploys APIM-related resources only; you provide the resources below.

## 1. Choose topology

| Need | Select | You provide |
| --- | --- | --- |
| Default deployment | Public, one `StandardV2` APIM | Publish the default APIM URL or your DNS/certificate separately. |
| Private gateway or zone redundancy | `PremiumV2` | Provide dedicated subnet(s), private DNS/routing, and test from in-network runners. |
| Regional gateway continuity | Optional second APIM | Provide secondary region/name; optionally a same-named secondary Foundry deployment set. |
| Public priority routing | Second APIM plus Traffic Manager | Own the enterprise hostname and traffic-change procedure. |

## 2. Prepare Azure and GitHub

- Create a Foundry account and three pinned deployment names; review direct Foundry local authentication and RBAC as release gates.
- Create the Entra caller application, audience, app role, assignments, consent, and GitHub smoke identity.
- Create the resource group, GitHub `poc` and protected `prod-primary` environments, OIDC federation, and versioned/soft-deleted external Blob state.
- For private or HA deployments, prepare subnets, DNS, routing, certificates, private endpoints, and self-hosted smoke runners.

## 3. Configure and validate

Follow the exact [GitHub configuration inventory](github-configuration.md). Run the read-only [Foundry preflight](foundry-preflight.md), then run `scripts/test/validate.sh` from a workstation with Bash, Python 3, ShellCheck, and OpenTofu.

## 4. Deploy and smoke

Dispatch `deploy` with a matching `environment_profile` and `networking_profile`. Review the sanitized plan summary; deployment regenerates inputs and plan, compares their summaries, and rejects non-equivalent results. Public deployments run hosted smoke. Private deployments require protected in-network `ha-smoke` evidence before release; operators own traffic changes.

## 5. Pilot clients and prepare for rollout

Generate and deploy [managed Claude Code settings](claude-code-managed-settings.md), run a [client canary](claude-code-canary.md), and complete the [production readiness](production-readiness.md) gates. Size APIM and approve Foundry quota using measured evidence, not local synthetic results.
