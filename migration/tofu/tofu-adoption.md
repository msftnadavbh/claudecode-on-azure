# OpenTofu existing-resource adoption

Use this runbook to adopt existing resources into the active OpenTofu deployment path. Prepare reviewed tfvars, remote state, a complete Azure resource inventory, and change approval first. The generated import manifest is a review aid, not proof of complete import coverage.

## Remote-state bootstrap prerequisites

Create the state storage **outside this configuration** before `tofu init`: an existing Storage Account and private blob container, with blob versioning and soft delete enabled. Configure the backend to use OIDC (no account keys or connection strings) and grant the deployment identity only the RBAC it needs to read and write that container (for example, **Storage Blob Data Contributor**). Ensure the identity can also acquire the AzureRM permissions required by the configuration. This repository does not create or import the state storage.

## Generate an import plan

`migration/tofu/generate_import_manifest.py` only writes a reviewable JSON manifest and shell commands. It never calls OpenTofu, Azure CLI, or an import itself. Supply actual IDs and deterministic existing role-assignment names:

```sh
python3 migration/tofu/generate_import_manifest.py \
  --subscription 11111111-1111-1111-1111-111111111111 \
  --resource-group gateway-rg \
  --primary-apim gateway-primary \
  --primary-foundry-account-id /subscriptions/.../resourceGroups/foundry-rg/providers/Microsoft.CognitiveServices/accounts/foundry-primary \
  --primary-foundry-role-assignment 22222222-2222-2222-2222-222222222222 \
  --var-file /secure/path/reviewed.tfvars.json \
  --observability managed --workspace-name gateway-logs --app-insights-name gateway-insights \
  --primary-monitoring-role-assignment 33333333-3333-3333-3333-333333333333 \
  --shell-output /secure/path/imports.sh --json-output /secure/path/imports.json
```

For secondary topology add `--secondary-apim`, its Foundry account ID and role-assignment GUID, and `--secondary-monitoring-role-assignment`; add `--traffic-manager-name` for Traffic Manager. Use `--observability external --workspace-id ... --app-insights-id ...` for shared telemetry; those two resources are recorded as excluded rather than imported. Pass existing `--action-group-id` and APIM integration `--primary-apim-subnet-id` (and `--secondary-apim-subnet-id`) so they are explicitly recorded as external too.

The manifest covers its currently generated APIM child resources, managed Foundry/monitoring role assignments, managed telemetry, diagnostics, alerts, and optional Traffic Manager resources. Existing Foundry accounts and external telemetry are excluded. Manually review all currently managed OpenTofu addresses and actual Azure objects; do not claim the manifest covers everything. Match `--observability` to the exact configuration before importing; omitted managed resources can appear as creates.

## Runtime baseline

The public single-region baseline is explicitly `StandardV2`, `zone_redundant = false`, and a measured fixed `APIM_DEFAULT_CAPACITY`. `APIM_SKU` and `APIM_ZONE_REDUNDANT` override those two baseline values in generated tfvars; private networking or zone redundancy requires `PremiumV2` at creation. Alerts retain Action Group actions only when `ACTION_GROUP_RESOURCE_ID` is supplied.

Concurrency limits are required and are approximate admission limits per APIM gateway: `PER_USER_CONCURRENT_STREAM_LIMIT` must be below `AGGREGATE_CONCURRENT_STREAM_LIMIT`, and the aggregate must be below the documented 2,048 connection ceiling. Select measured operational headroom rather than using the ceiling. The Foundry circuit breaker opens after 50 backend 5xx responses in one minute and remains open for one minute; it does not trip on 429 responses or use `Retry-After`.

Default addresses match `infra/tofu`. If the configuration is intentionally refactored, pass `--address KEY=ADDRESS` before reviewing and manually running the generated commands. Keys are the dotted resource names in the JSON manifest.

Review the JSON, tfvars, and generated shell file; resolve every existing model named value before apply; run `tofu init` with the pre-created remote backend, then run commands one at a time from the repository root. Do not import the same Azure object at more than one address. After every import batch, require a no-change plan; investigate every create, update, replace, or delete action before proceeding.
