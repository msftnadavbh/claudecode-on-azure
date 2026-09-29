# GitHub deployment configuration

Configure this inventory in the GitHub environment selected by the workflow. Create GitHub environments, Azure federated identities, and external Blob state first. The workflow uses OIDC and does not create identities, environments, state storage, or reviewer rules.

`deploy` accepts `environment_profile` (`poc` or `prod`), `networking_profile` (`public` or `private`), `deployment_mode` (`existing` default or `greenfield`), and Marketplace acceptance. Its `prod` input maps to the `prod-primary` GitHub environment; `poc` maps to `poc`. The networking input must match `APIM_NETWORKING_PROFILE` for **every** profile, including `poc`. Do not change mode for an existing state; greenfield needs a new state key.

## Secrets

| Secret | Required when | Purpose |
| --- | --- | --- |
| `AZURE_RESOURCE_GROUP` | Always | Existing gateway resource group in `existing`; new resource group name in `greenfield`. |
| `AZURE_CLIENT_ID` | Always | OIDC deployment identity client ID. |
| `AZURE_TENANT_ID` | Always | Tenant for Azure login. |
| `AZURE_SUBSCRIPTION_ID` | Always | Target subscription for APIM resources. |
| `AZURE_SMOKE_CLIENT_ID` | Public smoke / `ha-smoke` | Federated smoke identity client ID. |

## Required variables

| Variables | Value |
| --- | --- |
| `AZURE_LOCATION`, `APIM_NAME`, `APIM_PUBLISHER_EMAIL`, `APIM_PUBLISHER_NAME` | Primary APIM identity and location. |
| `ENTRA_TENANT_ID`, `APIM_EXPECTED_AUDIENCE`, `APIM_REQUIRED_APP_ROLE` | Caller-token validation. Both smoke workflows export `APIM_TENANT_ID` from `vars.ENTRA_TENANT_ID`, not from the infrastructure login tenant, and `APIM_AUDIENCE` from `APIM_EXPECTED_AUDIENCE`. |
| `FOUNDRY_BASE_URL`, `FOUNDRY_SUBSCRIPTION_ID`, `FOUNDRY_RESOURCE_GROUP`, `FOUNDRY_ACCOUNT_NAME` | Existing Foundry target. The URL is `https://<account>.services.ai.azure.com/anthropic`. Greenfield reuses only `FOUNDRY_ACCOUNT_NAME` and derives the rest in the target subscription. |
| `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Three existing, allowlisted deployment names. |
| `PER_USER_RATE_LIMIT`, `PER_USER_TOKEN_LIMIT`, `PER_USER_CONCURRENT_STREAM_LIMIT`, `AGGREGATE_CONCURRENT_STREAM_LIMIT` | Measured controls; require concurrency `per-user < aggregate < 2048`. Shared RPM applies to both inference operations; TPM applies to messages only. Controls are gateway-local and approximate. |
| `APIM_SKU`, `APIM_ZONE_REDUNDANT`, `APIM_DEFAULT_CAPACITY` | `StandardV2`, `false`, and a measured fixed capacity for the public baseline. |
| `TOFU_STATE_SUBSCRIPTION_ID`, `TOFU_STATE_RG`, `TOFU_STATE_STORAGE_ACCOUNT`, `TOFU_STATE_CONTAINER`, `TOFU_STATE_KEY` | Existing Azure Blob backend coordinates. |

For greenfield also configure `FOUNDRY_PROJECT_NAME`, `FOUNDRY_LOCATION`, `CLAUDE_MODEL_DEPLOYMENT_NAME`, `CLAUDE_MODEL_NAME`, `CLAUDE_MODEL_VERSION`, `CLAUDE_MODEL_SKU`, `CLAUDE_MODEL_CAPACITY`, `CLAUDE_ORGANIZATION_NAME`, `CLAUDE_COUNTRY_CODE`, and `CLAUDE_INDUSTRY`. The Marketplace checkbox authorizes OpenTofu/modelProviderData to accept Anthropic Marketplace terms and incur billing; do not configure secondary Foundry or private networking in greenfield. Greenfield creates the named resource group, so the deployment identity needs subscription-level permission to create that resource group; ongoing resources and role assignments can be scoped appropriately.

## Optional and conditional variables

| Variables | When required / behavior |
| --- | --- |
| `PER_USER_MONTHLY_TOKEN_QUOTA` | Optional integer 0..9223372036854775807; unset/blank/0 disables it. No positive default. Keep disabled until live policy validation. See [quota semantics](security.md#optional-monthly-token-quota). |
| `DEPLOY_SECONDARY` | Defaults to `false`. When `true`, require `AZURE_SECONDARY_LOCATION` and `APIM_SECONDARY_NAME`. A blank secondary Foundry URL uses the primary target. |
| `SECONDARY_FOUNDRY_BASE_URL`, `SECONDARY_FOUNDRY_SUBSCRIPTION_ID`, `SECONDARY_FOUNDRY_RESOURCE_GROUP`, `SECONDARY_FOUNDRY_ACCOUNT_NAME` | Provide all four to use a secondary Foundry target; its deployment names must match the primary names. |
| `APIM_NETWORKING_PROFILE` | Defaults to `public`. Set `private` only with `PremiumV2` and `APIM_SUBNET_RESOURCE_ID`; also supply `APIM_SECONDARY_SUBNET_RESOURCE_ID` when deploying secondary. |
| `LOG_ANALYTICS_WORKSPACE_RESOURCE_ID`, `APPLICATION_INSIGHTS_RESOURCE_ID` | Supply both to reuse external telemetry, or neither for repository-created telemetry. External Application Insights must have local auth disabled. |
| `ACTION_GROUP_RESOURCE_ID` | Existing incident destination; optional in configuration, required before rollout. |
| `TRAFFIC_MANAGER_ENABLED`, `TRAFFIC_MANAGER_NAME` | Defaults to `false`; only effective for public secondary topology. Name is optional and otherwise derives from the primary APIM name. |
| `CLAUDE_DESKTOP_DELEGATED_AUTH_ENABLED` | Defaults to `false`. When `true`, also require `CLAUDE_DESKTOP_CLIENT_ID` and `CLAUDE_DESKTOP_DELEGATED_SCOPE` (short `scp` claim value). Desktop remains preview-only. |

## OIDC, state, and review responsibilities

Use immutable GitHub-environment/repository/branch subject claims for deployment and smoke federated credentials. Grant the deployment identity AzureRM and Blob access required for the target and state container; use Azure AD/OIDC backend authentication, not storage keys. Create a private Blob container with versioning and soft delete, and control state access.

Protect `prod-primary` with required reviewers. The plan job initializes the backend before preflight, then creates Foundry preflight, run context, and a sanitized plan summary. The deploy job checks commit, generated inputs, provider lock, target subscription, state coordinates, and summary equivalence, reruns the applicable read-only preflight immediately before replan/apply, and rejects delete/replacement changes. Greenfield preflight permits an existing named resource group only for a partial-apply retry when the resource-group address already exists in the current state. The summary proves equivalent planned changes, **not** human-readable semantic intent; reviewers must still inspect source, inputs, and summary. Raw plans, state, and raw attestation fields are not retained; the generated tfvars are represented only by their hash.

## HA smoke environment values

Deployment smoke supplies all three model variables to the shared [smoke adapter](client-authentication.md#standalone-smoke-inputs): existing-mode values per role, or the one greenfield deployment for each role. Token counting checks all three mappings; only Sonnet performs inference. The app-only identity and outer retry loop are unchanged; no negative identities are autoenabled.

The protected `ha-smoke` workflow uses `prod-primary`, `AZURE_SMOKE_CLIENT_ID`, `AZURE_TENANT_ID`, and these environment variables: `ENTRA_TENANT_ID`, `APIM_EXPECTED_AUDIENCE`, the three model deployment variables, `APIM_PRIMARY_BASE_URL`, optional `APIM_SECONDARY_BASE_URL`, and optional `APIM_FAILOVER_BASE_URL`. URLs include `/claude`, for example `https://<apim-name>.azure-api.net/claude`; set the failover URL to your selected endpoint or the Traffic Manager FQDN plus `/claude`. Run it only from the required labeled, in-network self-hosted runner. Configure the caller tenant variable before updating the helper. The federated smoke identity must be able to obtain the audience token in that caller tenant; differing infrastructure and caller tenants do not imply cross-tenant consent or access.
