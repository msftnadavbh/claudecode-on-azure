# OpenTofu Deployment Migration Plan

Status: Prepared; Live Adoption Blocked

## Scope

Replace only the Azure deployment implementation with OpenTofu. Preserve runtime policies, client tooling, existing resources, names, identities, networking, telemetry behavior, and smoke/load gates. Keep Bicep as a temporary rollback reference until OpenTofu adoption stabilizes.

## Architecture

- AzAPI manages the APIM parent with the existing preview API contract.
- AzureRM manages mature APIM children, monitoring, RBAC, autoscale, and Traffic Manager resources.
- Existing Foundry accounts, subnets, Action Group, and optional shared telemetry remain external.
- One remote Azure Blob state key per environment; production primary and secondary remain in one state.
- GitHub OIDC authenticates state and Azure operations; no storage keys or client secrets.

## Execution

1. Build and statically validate OpenTofu parity configuration.
2. Generate a deterministic import manifest matching the HCL addresses.
3. Configure the externally managed state backend and OIDC permissions.
4. Import PoC resources and require a zero-change plan.
5. Import production resources and require a reviewed zero-change plan.
6. Replace Bicep workflow execution with exact saved-plan apply only after adoption.
7. Retain Bicep compilation for one stabilization release, then remove it separately.

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
- Python unit tests: 20 passed.
- Bicep rollback-reference compilation: passed.
- Aggregate repository validation: passed (20 tests).
- Remote backend access, state imports, and live plan: blocked until external state/OIDC prerequisites are configured.

## Role Assignment Verification

- APIM system identities receive Foundry User on the exact existing Foundry account resource IDs.
- APIM system identities receive Monitoring Metrics Publisher on the exact selected Application Insights resource.
- Assignment UUIDs reproduce the existing Bicep `guid(scope, principal, role)` values.
- Foundry and telemetry subscriptions use explicit AzureRM provider aliases.
