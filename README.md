# Claude Code Enterprise Gateway on Azure

Deploy a governed Claude Code gateway that authenticates callers with Microsoft Entra, applies controls in Azure API Management (APIM), and calls Microsoft Foundry Claude deployments with APIM's managed identity. Configure and operate managed clients through the native Anthropic Messages API without direct Foundry credentials.

## What this deploys

- `/claude` on APIM, with native `/v1/messages` and `/v1/messages/count_tokens`, authenticated `/v1/models`, unbuffered SSE, and APIM-local unauthenticated `/health`.
- A fixed-capacity, public, single-region `StandardV2` APIM baseline. Use `PremiumV2` only for zone redundancy or private VNet injection.
- Optional second APIM and public Traffic Manager. You provide private DNS, failover, custom DNS, and certificates.
- APIM policy, managed identity access to Foundry, optional telemetry and alerts, and managed Claude Code configuration generators. In `greenfield` mode it also creates a new resource group, one AIServices Foundry account, one project, and one Claude deployment.
- Bundled macOS/Linux/WSL and native Windows Entra token helpers, managed Claude Code settings, and optional Desktop configuration. Per-principal monthly token quota defaults to **disabled**; enabled native quotas are advisory controls, not dollar caps.
- Read-only discovery of deployed Claude models, a shared gateway catalog, and an opt-in daily collection workflow. Discovery reports new catalog candidates; it never deploys models automatically.

![Conceptual Claude Code Enterprise Gateway on Azure architecture. The written implementation boundary below is authoritative.](assets/architecture/claude-code-enterprise-gateway.png)

`Claude Code → Microsoft Entra ID → Azure API Management → Microsoft Foundry → your Claude deployments`

## Before you begin

Choose one immutable state mode. `existing` (default) adopts your existing resource group and cross-subscription Foundry account with three deployment names. `greenfield` creates a new target-subscription resource group, AIServices/S0 Foundry account, project, and exactly one public Claude deployment; that deployment is mapped to the Opus, Sonnet, and Haiku roles. Use a new Blob state key for greenfield and never switch mode for an existing state.

You still provide external Blob state/container, Entra caller app/roles/consent, GitHub identities/environments/OIDC, VNet/DNS/certificates/private endpoints, Action Group, and client installation/management. Greenfield is public-only, creates no Entra/GitHub/state/network resources, and its Marketplace checkbox authorizes OpenTofu/modelProviderData to accept Anthropic Marketplace terms and incur billing. See [getting started](docs/getting-started.md) and the [GitHub configuration inventory](docs/github-configuration.md).

## Deploy

1. Configure [GitHub environments, OIDC, state, secrets, and variables](docs/github-configuration.md).
2. Run the read-only [Foundry preflight](docs/foundry-preflight.md) and repository validation (local tests/compilation and OpenTofu initialization; not a read-only command).
3. Dispatch the protected `deploy` workflow with matching `environment_profile` and `networking_profile`.
4. Retain public smoke evidence, or run protected in-network `ha-smoke` for private or HA deployments.

OpenTofu is the only active deployment path: OpenTofu `1.12.3`, AzureRM `4.56.0`, and AzAPI `2.12.0`. Existing-mode role pins still define defaults, while runtime model discovery and acceptance are now driven by live Foundry inventory through `/v1/models` and backend validation. The optional [reviewed model catalog](docs/model-discovery.md) remains a governance artifact for discovery review workflows.

## Configure Claude Code

Use the bundled helpers on macOS, Linux, WSL, and native Windows; supply the caller tenant UUID and audience, then pilot the installed client on each OS. [Configure managed Claude Code settings](docs/claude-code-managed-settings.md) and run the [client canary](docs/claude-code-canary.md). Claude Desktop is an optional preview; a [local Gateway-mode Chat pilot](docs/windows-desktop-pilot.md) worked without registry policy or a new OIDC client.

[Shared model discovery](docs/model-discovery.md) is opt-in for both clients. Both configuration generators accept `--enable-model-discovery`; enable it only after the owning gateway publishes `/v1/models`. The guide covers catalog collection, reviewed publication, client configuration, and rollback.

### Live pilot status — 26 October 2026

- The existing gateway now serves an authenticated discovery endpoint with **Opus 5.5 (default)** and **Opus 5**. Valid credentials returned the catalog; missing and malformed credentials returned `401`.
- The documented Windows Desktop pilot is configured for discovery with its existing helper and authentication preserved. Its next-launch picker and end-to-end inference have not been verified.
- Runtime model discovery is **dynamic** from Foundry inventory. The daily collector remains disabled until configured, and reviewed catalog publication is a separate governance step.
- Only the discovery operation/policy and the single-PC profile were changed. **Full OpenTofu adoption remains pending**: live API identifiers and authentication still differ from the repository baseline, so do not apply the full configuration blindly.

See the [bounded publication record](docs/model-discovery.md#2026-10-26-bounded-live-pilot--configuredapi-verified) and [Windows Desktop record](docs/windows-desktop-pilot.md#2026-10-26-discovery--configuredapi-verified) for evidence and recovery boundaries.

## Validate

Run commands directly from this standalone repository root (`claudecode-prod/`,
containing this README). The retained `claudecodepoc-hard/` directory is an ignored
historical checkout, not a runtime dependency; do not change into it. Paths in
`findings.md` describe the earlier checkout and remain historical evidence.

Quick offline checks (fake credentials only; no provider initialization):

```bash
python3 -B -m unittest discover -s scripts/test -p 'test_*.py'
python3 -B migration/tofu/test_generate_import_manifest.py
```

Full validation requires Bash, Python 3, ShellCheck, and OpenTofu:

```bash
scripts/test/validate.sh
```

This checks repository configuration and local tools; Python compilation writes bytecode and OpenTofu initialization installs the providers pinned in `infra/tofu/.terraform.lock.hcl`. The first full validation needs network access to download any providers not already available locally or cached; it is not an offline-only check. Native Windows helper tests skip on Linux: verify the actual installed helper on Windows. It does not prove Foundry quota, APIM capacity, private connectivity, SLOs, failover, or client-fleet behavior; use the [production readiness gates](docs/production-readiness.md) before rollout.

## Documentation

- [Documentation](docs/index.md)
- [Architecture](docs/01-architecture.md)
- [Networking and availability](docs/networking.md) and [operations](docs/operations-runbook.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Opus 5.5 live pilot](docs/opus-5-5-pilot.md), [Windows Desktop Chat pilot](docs/windows-desktop-pilot.md), and [temporary native quota rehearsal](docs/live-budget-demo.md) (focused evidence, **not** a full IaC deployment)
