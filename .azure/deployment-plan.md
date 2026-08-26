# OpenTofu Deployment Migration Plan

Status: **STATE B — OpenTofu is the preferred, active deployment path; Bicep is deprecated and non-authoritative.**

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

## Validation Proof

- `tofu fmt -check -recursive`: passed.
- `tofu init -backend=false -input=false -lockfile=readonly`: passed.
- `tofu validate`: passed.
- Python unit tests and migration tests pass in aggregate repository validation.
- Aggregate repository validation: passed.
- Remote backend access, state imports, and live plan: blocked until external state/OIDC prerequisites are configured.
- Read-only Azure check: current subscription contains no APIM instance and no OpenTofu backend variables are configured; no live import/plan was attempted.

## Role Assignment Verification

- APIM system identities receive Foundry User on the selected existing or greenfield Foundry account resource IDs.
- APIM system identities receive Monitoring Metrics Publisher on the exact selected Application Insights resource.
- Assignment UUIDs reproduce the existing Bicep `guid(scope, principal, role)` values.
- Foundry and telemetry subscriptions use explicit AzureRM provider aliases.
