# Operations and rollback

Use this runbook for common operational failures and controlled rollback. Keep approved access to your resources and a last-known-good source revision. For repository-managed resources, rollback is reviewed and non-destructive OpenTofu; it cannot include deletion or replacement because the workflow rejects those changes.

| Condition | Behavior | Operator action |
| --- | --- | --- |
| User/helper authentication failure | No fallback credential | Reauthenticate Azure CLI and verify Entra assignment/Conditional Access. |
| Foundry 429 | Passed through; no retry or breaker trip | Check quota/limits; retry only where client policy permits. |
| Foundry 5xx | Breaker opens after 50 backend 5xx/minute | Resolve backend issue and observe closure; no POST replay. |
| APIM saturation | Approximate local admission limits apply | Reduce load or deploy reviewed, measured fixed capacity. |
| Regional/APIM failure | Optional public Priority routing automatically reselects healthy primary when it recovers, subject to DNS caching | Observe gateway and DNS recovery; no manual hold-down is implemented. Private DNS failover/failback remains operator-owned. |
| Telemetry gap | Inference continues | Repair destination; do not enable payload capture. |

## Rollback

**Live pilot exception (2026-10-26):** [bounded discovery publication and recovery boundary](model-discovery.md#2026-10-26-bounded-live-pilot--configuredapi-verified) records the operation/policy and single-PC change as **configured/API-verified**, not full IaC adoption or GUI verification. The scoped pilot operator owns those new resources pending adoption. Do not apply the broader repository or the workflow rollback instructions below to that pilot: live API IDs/authentication still diverge, and adoption must account for the new operation/policy. Recovery requires a closed Desktop, matching backup/profile/metadata/helper/ACL baseline, owned-resource ETags and a reviewed plan; user/app drift requires manual review. The owner must retain/archive the private audit bundle before cleanup; runtime does not depend on it.

For repository-managed resources, dispatch the protected workflow from a compatible last-known-good source revision. Review the regenerated OpenTofu plan and summary; apply only when it contains no delete/replacement action and integrity checks pass. Do not restore state or make portal-only APIM edits. Roll back clients by redeploying the prior managed settings and helper through device management. Roll back Foundry models separately.

For repository-managed [shared model discovery](model-discovery.md), the `models` operation and its operation policy exist even when no catalog is configured. Once deployed, record that discovery-capable revision as the **oldest compatible rollback baseline** for this feature. Revisions predating it would delete these resources; the existing `scripts/tofu/plan_summary.py` destructive-change gate rejects that rollback.

To disable catalog-driven expansion, unset `MODEL_CATALOG_FILE` in the owning workflow's protected configuration and review/apply the non-destructive policy update from a compatible revision. `GET /v1/models` remains with the deduplicated role-pin fallback, and inference membership returns to the configured pins. Undo client opt-in through the client owner using prior settings/fixed-list backups. Removing the operation/policy instead requires a separately approved deletion path, not the standard rollback workflow; **do not relax the destructive-change gate**.

For private/HA drills, `ha-smoke` is observer-only. It retains evidence; operators separately perform approved traffic changes. See [troubleshooting](troubleshooting.md) for symptom-based recovery.

Public Traffic Manager health probes are gateway-local, not Foundry/model checks. Primary reselection affects new DNS answers; resolver and client caches govern when new connections move. Existing streams do not migrate, and failed inference POSTs are not replayed. Compare actual primary/secondary model, version, and upgrade policy before approving recovery; a healthy `/claude/health` alone is insufficient.
