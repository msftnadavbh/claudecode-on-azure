# Claude Code Enterprise Gateway on Azure

Deploy a governed Claude Code gateway that authenticates callers with Microsoft Entra, applies controls in Azure API Management (APIM), and calls Microsoft Foundry Claude deployments with APIM's managed identity. Configure and operate managed clients through the native Anthropic Messages API without direct Foundry credentials.

## What this deploys

- `/claude` on APIM, with native `/v1/messages` and `/v1/messages/count_tokens`, authenticated `/v1/models`, unbuffered SSE, and APIM-local unauthenticated `/health`.
- A fixed-capacity, public, single-region `StandardV2` APIM baseline. Use `PremiumV2` only for zone redundancy or private VNet injection.
- Optional second APIM and public Traffic Manager. You provide private DNS, failover, custom DNS, and certificates.
- APIM policy, managed identity access to Foundry, optional telemetry and alerts, and managed Claude Code configuration generators. In `greenfield` mode it also creates a new resource group, one AIServices Foundry account, one project, and one Claude deployment.
- Bundled macOS/Linux/WSL and native Windows Entra token helpers, managed Claude Code settings, and optional Desktop configuration. Per-principal monthly token quota defaults to **disabled**; enabled native quotas are advisory controls, not dollar caps.
- Dynamic, authenticated discovery of deployed Anthropic models from the bound Foundry account's ARM inventory, plus a separate opt-in daily governance collector. Neither discovery path deploys models.

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

OpenTofu is the only active deployment path: OpenTofu `1.12.3`, AzureRM `4.56.0`, and AzAPI `2.12.0`. After an approved deployment, `/v1/models` reads ARM deployment inventory with APIM's managed identity; it does **not** proxy the unsupported Foundry `/anthropic/v1/models` route. Inference model validation remains backend-owned. Role pins remain configuration, not an inventory allowlist or protection against retargeting an existing deployment name. The optional [reviewed model catalog](docs/model-discovery.md) is a separate governance artifact. **The bounded live publication below is operation-only, not deployment of the whole repository API policy or full IaC.**

## Configure Claude Code

Use the bundled helpers on macOS, Linux, WSL, and native Windows; supply the caller tenant UUID and audience, then pilot the installed client on each OS. [Configure managed Claude Code settings](docs/claude-code-managed-settings.md) and run the [client canary](docs/claude-code-canary.md). Claude Desktop is an optional preview; a [local Gateway-mode Chat pilot](docs/windows-desktop-pilot.md) worked without registry policy or a new OIDC client.

For macOS/Linux Terminal, follow the [single-platform quick start and installation checks](docs/claude-code-managed-settings.md#macos-and-linux-terminal-quick-start); `--platform macos` or `--platform linux` avoids requiring unrelated OS helper paths. For macOS Desktop, use the [managed preview rollout](docs/desktop-deployment.md#macos-managed-preview-rollout), including profile deployment, discovery and rollback gates. Linux users should use Terminal, not Desktop.

## Automatic model discovery

After the dynamic reader is published, adding or removing a successful Anthropic/Claude deployment in the **same bound Foundry account** is reflected on a fresh gateway inventory read, **without a gateway redeploy**. Neither the reader nor the separate governance collector deploys models. Freshness is **30-second gateway cache + ARM propagation + client startup refresh**: it is not instant and does not poll an already-open picker. Configured default pins are not automatically upgraded; missing pins are not fabricated and may leave a client choosing the first remaining model.

- **Terminal Claude Code:** discovery is off by default. Set `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` in the approved client environment, or append `--enable-model-discovery` to the [managed-settings generator](docs/claude-code-managed-settings.md). Preserve the existing `ANTHROPIC_BASE_URL`, `apiKeyHelper` and role pins. Restart Claude Code, then inspect `/model`; `availableModels` and `modelPicker.replaceBuiltInOptions` can hide discovered entries. This does not mean discovery is already enabled in any local CLI.
- **Desktop:** after owner-approved backup/configuration review, use the [generator's](docs/desktop-deployment.md) `--enable-model-discovery` option: it sets `modelDiscoveryEnabled` and omits/removes the explicit `inferenceModels` list, which otherwise wins. The verified local pilot is a different helper-script profile, not that generated MDM/OIDC configuration. **Fully quit Desktop before restarting**; closing its window can leave background processes running.

**CLI latency caveat:** its default discovery deadline is **3 seconds**, with no redirects. The live gateway's first cold read took **7.204 seconds** (helper acquisition was a separate 5.724 seconds), not an SLO or warm benchmark. A timeout can leave cached/fallback models. Windows Desktop success does **not** prove terminal discovery works. See [discovery bounds and verification limits](docs/model-discovery.md#freshness-bounds-and-failures).

### Repository integration coverage versus live discovery verification

| Client / OS | Repository integration coverage | Live discovery verified on 26 October 2026 |
| --- | --- | --- |
| Claude Code terminal — macOS / Linux / WSL / native Windows | Bundled helpers and generated settings supported | **NOT live-verified on any terminal OS** in this check. Historical Linux inference is separate; native Windows managed-mode execution remains unverified. |
| Desktop — Windows | Windows configuration generator available | **3.6556.2.0**, actual **local Gateway/helper-script**, **not MDM/OIDC**: fresh four-model picker observed; **Opus 5.5 selected**. No new inference test. |
| Desktop — macOS | `.mobileconfig` generator available | Actual device, native authentication and picker **UNTESTED**. |
| Desktop — Linux | Desktop integration **not provided/validated by this repository** | No Linux Desktop installer/configuration claim; use the Terminal integration. |

### Live pilot status — 26 October 2026

- The existing `models` **operation policy** now reads dynamic inventory: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5`, then `claude-opus-5`. The first three carry native family-default metadata. Authenticated bare GET returned `200`; missing auth returned `401`. No new denied-principal or malformed-token check was performed in this run.
- Windows Desktop **3.6556.2.0** freshly discovered four models; the visible enabled picker showed **Opus 5.5 selected**, Sonnet 5.5, Haiku 4.5 and Opus 5. This was the Code-view model selector, not a new Chat inference or Code-tools workflow test. No inference was sent.
- This publication changed **only the existing operation policy**: parent authentication, other cloud resources and the Desktop profile were preserved. The daily governance collector remains artifact-only and disabled until configured. Live add/remove/empty mutations, aliases/refusal fallback, revocation, long-lived refresh and fleet behavior were not verified.
- **Full OpenTofu adoption remains pending**: live API identifiers and stricter authentication still differ from the repository baseline. Do not apply the full configuration or an old profile backup blindly.

See the [dynamic publication record](docs/model-discovery.md#2026-10-26-dynamic-discovery--api-and-windows-picker-verified) and [Windows Desktop record](docs/windows-desktop-pilot.md#2026-10-26-dynamic-discovery--api-and-picker-verified) for evidence, untested paths and recovery boundaries. Earlier static-stage records are retained as superseded history.

## Validate

Run commands directly from this standalone repository root (`claudecode-prod/`,
containing this README). The retained `claudecodepoc-hard/` directory is an ignored
historical checkout, not a runtime dependency; do not change into it. Paths in
`findings.md` describe the earlier checkout and remain historical evidence.

Quick offline checks (fake credentials only; no provider initialization). The policy logic suite requires OpenTofu and an installed .NET SDK with its bundled Newtonsoft.Json assembly; it fails rather than silently skipping C# execution:

```bash
python3 -B -m unittest discover -s scripts/test -p 'test_*.py'
python3 -B migration/tofu/test_generate_import_manifest.py
```

The C# suite compiles the real rendered/XML-decoded policy expressions, without NuGet restore or downloads. An explicit native C# compiler/assembly can also be supplied for a local WSL check; see [test toolchains and limits](docs/model-discovery.md#offline-policy-logic-tests). The ordinary unittest discovery above and CI's existing validation command both include it.

Full validation requires Bash, Python 3, ShellCheck, OpenTofu, and the C# test toolchain:

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
