# Security

This page describes the gateway's identity and telemetry controls. You provide the Entra application and assignments, and review Foundry security. This repository does not create Entra registrations, remove other Foundry RBAC, or secure workstations. Greenfield creates its Foundry account with local authentication disabled; existing mode does not alter existing Foundry security settings.

The policy below is the repository design, **not** the [strict live pilot policy](opus-5-5-pilot.md) (CLI app/user/role/scope all required). The [local Desktop Chat pilot](windows-desktop-pilot.md) used the existing helper-script CLI credential path, not the unused Desktop OIDC registration; full IaC adoption remains unvalidated.

## Identity and credential boundary

- APIM validates tenant, audience, `oid`, `tid`, and the configured app role. The optional Desktop preview can instead use its configured client ID and exact delegated scope.
- APIM deletes caller `Authorization`, API-key, subscription-key, and legacy credential query values before requesting Foundry with its managed identity.
- APIM receives `Foundry User` on your Foundry account. Before rollout, separately assess direct Foundry local authentication and existing direct inference RBAC.
- Existing mode allowlists three configured deployment names; greenfield maps one managed deployment to all three Claude roles. Do not put shared provider credentials or direct Foundry settings on client devices.

## Diagnostics and clients

APIM diagnostics collect no bodies or selected headers; IP collection is disabled. Safe traces hold request ID, tenant, validated identity, and operation. Success is sampled at 10%; errors are retained. When you supply telemetry, disable local authentication on that Application Insights resource.

Managed Claude Code settings use credential refresh and subprocess environment scrubbing. Scrubbing is not process isolation; device management owns installation, permissions, version pinning, updates, and rollback. Desktop is disabled by default and remains an optional preview.

## Optional monthly token quota

`per_user_monthly_token_quota` / `PER_USER_MONTHLY_TOKEN_QUOTA` is a uniform principal limit, including app-only CI, not a user-specific budget map. Zero (the default, including unset/blank workflow values) disables monthly enforcement. A positive signed-64-bit integer selects one `llm-token-limit` policy combining TPM and a Monthly token quota; otherwise exactly one TPM-only policy executes. Token counting is not charged against token quota; both inference operations share RPM.

`callerKey` remains `tid:oid`. RPM counters use `claude-foundry:rpm:<tid>:<oid>` and both token branches use `claude-foundry:tokens:<tid>:<oid>`. These new namespaces have **no continuity or backfill** from the old counters. The enabled branch exposes `x-remaining-user-monthly-tokens`; it is advisory, not a billing ledger.

The policy attribute is [`remaining-quota-tokens-header-name`](https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy); its output header remains `x-remaining-user-monthly-tokens`. APIM compiles both branches even when quota is zero, so default-disabled is not a safeguard against invalid attributes. The offline source-referenced allowlist checks only `llm-token-limit` attribute names in every branch, not other policy elements, and is not an APIM compiler.

This is not a dollar cap: streaming token estimates, concurrent-request overshoot, and gateway-local counters prevent exact global spend enforcement. Separate gateways/failover can maintain separate quota state. Live compilation and TPM/streaming validation are required even with quota disabled. Keep monthly quota disabled until its separate live accounting tests pass; separately test prompt-cache effects and concurrency/overshoot on the deployed tier/model. Offline XML tests do not prove runtime acceptance or accounting accuracy.
