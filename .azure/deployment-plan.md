# OpenTofu Deployment Migration Plan

Status: **Focused Opus 5.5 gateway/CLI and local Windows Desktop Chat pilots verified; temporary monthly-quota rehearsal restored; full OpenTofu adoption remains unvalidated.**

The focused live work upgraded the model and strict APIM Entra pilot authentication, verified Linux Claude Code and local Windows Desktop Chat via its existing helper-script Gateway configuration, and temporarily installed then removed a native monthly quota. See [gateway/CLI](../docs/opus-5-5-pilot.md), [Desktop](../docs/windows-desktop-pilot.md), and [quota rehearsal](../docs/live-budget-demo.md) for evidence and limits. The historical inventory/validation below predates these pilots; it does not describe the current API authorization or model inventory and does **not** authorize a full IaC apply.

## Current deployment request

- Deploy only to subscription `68eab0d1-ab81-4851-b2dd-173dede87582` (`MCAPS-Hybrid-REQ-162389-2026-nadavbh`).
- Tenant: `fdpo.onmicrosoft.com`, tenant ID `16b3c013-d300-468d-ac64-7eda0820b6d3`.
- OpenTofu remains the active deployment path; Bicep is deprecated and non-authoritative.
- Existing target: `claudepoc-rg`, `eastus2`; APIM `apim-claudecode-project-test-01` (StandardV2, capacity 1); Foundry `project-test-01`, project `proj-default`, existing `claude-opus-5` and pilot `claude-opus-5-5` version `2` (GlobalStandard, capacity 40 for the pilot deployment).
- Preserve existing resources; use existing mode rather than greenfield. Caller identity configuration and remote state ownership remain unresolved.
- All writable provider, backend, RBAC, and telemetry scopes must remain in the authorized subscription. Do not use cross-subscription defaults or create replacement resources without approval.
- Next steps: refresh read-only inventory; confirm deployment inputs/state ownership, API/backend identifiers and strict pilot authorization; validate and review a non-destructive plan; deploy only after prerequisites pass.
- Historical migration evidence below does not validate this deployment or authorize cross-subscription access.

### Historical pre-pilot inventory and blockers (not current configuration)

- Read-only inventory at that time confirmed all candidate resources were in the authorized subscription and tenant; this line does not describe later pilot changes.
- APIM is provisioned with system-assigned identity and public networking. Its existing API ID is `claude-api`, path `/claude`; **subscription keys were required before the pilot, but are now disabled on this API with strict Entra validation**. IaC currently hardcodes API ID `claude` and a different backend ID; reviewed adoption/name-compatibility and authorization reconciliation are required before applying, not a duplicate API or destructive replacement.
- Foundry local authentication is disabled. Existing model upgrade policy is `OnceNewDefaultVersionAvailable`; no upgrade-policy change has been authorized or made.
- No local ARM/backend environment variables are configured. Target inventory found no dedicated deployment-state storage; the governance storage account must not be repurposed implicitly.
- The `msftnadavbh/claudecode-on-azure` GitHub environment listing returned no environments. Protected deployment/OIDC/state prerequisites are not established by this inventory.
- Required next decisions: provide the existing state owner/backend coordinates or approve dedicated state bootstrap; confirm adoption of the existing gateway, current strict caller Entra configuration, and deployment route. Do not re-enable key-only access or replace strict pilot authorization with the repository's broader role-OR-Desktop design without approval.

## Scope

OpenTofu is the preferred, active Azure deployment implementation. Preserve runtime policies, client tooling, existing resources, names, identities, networking, telemetry behavior, and smoke/load gates. Bicep remains only under `migration/bicep` as a deprecated, non-authoritative migration reference.

## Architecture

- AzAPI manages the APIM parent with the existing preview API contract.
- AzureRM manages mature APIM children, monitoring, RBAC, and Traffic Manager resources.
- Existing mode keeps Foundry accounts external; greenfield creates its resource group, Foundry account, project, and one Claude deployment. Subnets, Action Group, and optional shared telemetry remain external.
- One remote Azure Blob state key per environment; production primary and secondary remain in one state.
- GitHub OIDC authenticates state and Azure operations; no storage keys or client secrets.

## Execution

1. Build and statically validate the active OpenTofu configuration.
2. Generate a deterministic import manifest matching the HCL addresses.
3. Configure the externally managed state backend and OIDC permissions.
4. Import PoC resources and require a zero-change plan.
5. Import production resources and require a reviewed zero-change plan.
6. Regenerate from the same commit and inputs, verify the redacted planned-change digests, and apply that verified equivalent plan.
7. Keep Bicep only under `migration/bicep` as a deprecated, non-authoritative reference. Final removal gate: remove it only after PoC and production imports, two zero-change plans, the first successful OpenTofu apply, and a rollback rehearsal.

## Safety Gates

- Never replace or destroy APIM in normal workflows.
- Reject delete and replacement actions in plans.
- Never upload state, raw plan JSON, credentials, prompts, or response bodies.
- Preserve deterministic role-assignment IDs and managed-identity telemetry authentication.
- Run public/private endpoint smoke and HA evidence after apply.

## External Prerequisites

- Existing Azure Storage account/container with versioning, soft delete, deletion protection, and Azure AD-only access.
- Plan/apply OIDC identities with state-container access and least-privilege Azure RBAC.
- Live resource inventory and reviewed import manifest.

## Historical local validation proof (not current full IaC validation)

- `tofu fmt -check -recursive`: passed.
- `tofu init -backend=false -input=false -lockfile=readonly`: passed.
- `tofu validate`: passed.
- Python unit tests and migration tests passed at the time in aggregate repository validation.
- Aggregate repository validation passed at the time; rerun on current changes before any adoption. `validate.sh` runs Python compilation and OpenTofu init (local writes), not a read-only cloud preflight. Native Windows helper tests skip on Linux and require an actual Windows pilot.
- Remote backend access, state imports, and live plan: blocked until external state/OIDC prerequisites are configured.
- Historical pre-migration Azure check found no APIM in the then-selected subscription. The currently locked subscription does contain the pilot APIM documented above; remote OpenTofu adoption remains pending.

## Role Assignment Verification

- APIM system identities receive Foundry User on the selected existing or greenfield Foundry account resource IDs.
- APIM system identities receive Monitoring Metrics Publisher on the exact selected Application Insights resource.
- Assignment UUIDs reproduce the existing Bicep `guid(scope, principal, role)` values.
- Foundry and telemetry subscriptions use explicit AzureRM provider aliases.
