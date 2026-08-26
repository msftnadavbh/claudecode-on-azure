# Migration and adoption

**Purpose:** choose a safe path for a new APIM deployment or adoption of an existing one. **Prerequisites:** customer owners for Foundry, Entra, state, networking, and change approval. **Boundary:** OpenTofu is the active deployment path.

## New APIM deployment

1. Prepare customer-owned Foundry deployments, Entra app/roles, GitHub OIDC/environments, Blob state, resource group, and selected networking.
2. Start with public, single-region `StandardV2` unless private injection or zone redundancy requires `PremiumV2`.
3. Configure [GitHub variables and secrets](github-configuration.md), run [Foundry preflight](foundry-preflight.md), and review the protected plan.
4. Deploy, run the applicable smoke evidence, pilot managed clients, then approve capacity and operational gates.

## Existing-resource adoption

Use the [OpenTofu adoption runbook](../migration/tofu/tofu-adoption.md). Its import manifest is a starting inventory, not proof of complete import coverage. Manually compare every current managed address and Azure object, resolve all existing model named values before apply, import deliberately, and require a no-change plan. Do not use new-deployment defaults to retier a live APIM resource.

Expand clients only after client canaries, measured limits, alerting, rollback review, and any selected private/HA evidence pass.
