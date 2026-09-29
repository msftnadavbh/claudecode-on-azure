# Operations and rollback

Use this runbook for common operational failures and controlled rollback. Keep approved access to your resources and a last-known-good source revision. Rollback is reviewed and non-destructive OpenTofu; it cannot include deletion or replacement because the workflow rejects those changes.

| Condition | Behavior | Operator action |
| --- | --- | --- |
| User/helper authentication failure | No fallback credential | Reauthenticate Azure CLI and verify Entra assignment/Conditional Access. |
| Foundry 429 | Passed through; no retry or breaker trip | Check quota/limits; retry only where client policy permits. |
| Foundry 5xx | Breaker opens after 50 backend 5xx/minute | Resolve backend issue and observe closure; no POST replay. |
| APIM saturation | Approximate local admission limits apply | Reduce load or deploy reviewed, measured fixed capacity. |
| Regional/APIM failure | Optional public Priority routing automatically reselects healthy primary when it recovers, subject to DNS caching | Observe gateway and DNS recovery; no manual hold-down is implemented. Private DNS failover/failback remains operator-owned. |
| Telemetry gap | Inference continues | Repair destination; do not enable payload capture. |

## Rollback

Dispatch the protected workflow from the last-known-good source. Review the regenerated OpenTofu plan and summary; apply only when it contains no delete/replacement action and integrity checks pass. Do not restore state or make portal-only APIM edits. Roll back clients by redeploying the prior managed settings and helper through device management. Roll back Foundry models separately.

For private/HA drills, `ha-smoke` is observer-only. It retains evidence; operators separately perform approved traffic changes. See [troubleshooting](troubleshooting.md) for symptom-based recovery.

Public Traffic Manager health probes are gateway-local, not Foundry/model checks. Primary reselection affects new DNS answers; resolver and client caches govern when new connections move. Existing streams do not migrate, and failed inference POSTs are not replayed. Compare actual primary/secondary model, version, and upgrade policy before approving recovery; a healthy `/claude/health` alone is insufficient.
