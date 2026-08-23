# Operations and rollback

| Failure | Detection / user symptom | Automatic mitigation | Operator action / recovery |
| --- | --- | --- | --- |
| User token expires | helper/auth error or 401 | helper asks MSAL for a current token | Reauthenticate Azure CLI; verify assignment/CA |
| Helper/Azure CLI unavailable | Claude request cannot start | none | Install/sign in; never substitute shared credentials |
| APIM MI token or RBAC failure | backend 401/403, users see provider error | none | Restore identity and `Foundry User`; redeploy RBAC |
| Foundry 429 | quota alert, streamed call fails | passes to client; no circuit trip or APIM retry | Check quota; client retries if appropriate |
| Foundry 500/503 | backend alert, streamed call fails | circuit opens after 50 backend 5xx in one minute; no APIM POST retry | Check backend health and observe closure |
| Primary region/DNS failure with HA enabled | Traffic Manager or private DNS health degraded | configured DNS failover | Run secondary smoke; repair primary; manual failback |
| Foundry/provider regional failure | backend alert/circuit opens; gateway health stays healthy | none | Validate the optional secondary target and manually fail over when beneficial |
| APIM saturation/connections | CPU/memory/latency alert | concurrent-stream admission; warm fixed capacity | Reduce load or deploy a measured higher fixed capacity |
| Client disconnect | incomplete stream traces | backend connection closes | No operator action unless rate spikes |
| Circuit open | 503 after backend 5xx failures | one-minute trip window | Resolve backend cause and observe closure |
| Telemetry unavailable/delayed | ingestion gap | inference continues | Repair diagnostic destination; do not enable bodies |
| Agent fan-out/morning surge | per-user 429, capacity/token pressure | per-user RPM/TPM fairness | Validate entitlement, limits, and aggregate quota |
| Deployment renamed/removed | backend model errors | none | Restore pinned deployment or controlled settings update |
| Claude Code alias behavior changes | wrong/failed model selection | pinned deployment env values | Halt rollout; regression-test and pin client version |

## Deployment rollback

Every deployment uses OpenTofu and API revision `1`. Before production approval, retain the previous successful commit and plan summary. Workflow apply regenerates from the same commit and inputs, verifies the redacted planned-change digests, and applies that verified equivalent plan. To roll back, dispatch the workflow at the prior commit, review the new plan for destructive changes, apply, and smoke every enabled region. Never restore state as an infrastructure rollback. Do not mutate customer-owned Foundry deployments through this repository.

For a policy-only incident, apply a newly reviewed plan from the last-known-good commit rather than editing APIM in the portal. `migration/bicep` is a deprecated, non-authoritative reference; using it changes Azure outside OpenTofu state and requires reconciliation.

## HA drill evidence

Use `.github/workflows/ha-smoke.yml` for observer-only readiness, failover, failback, and rollback evidence. URLs come only from the protected environment, and execution requires a labeled in-network self-hosted runner. The artifact contains endpoint hostnames and resolved addresses but no token or model output; retain it for 90 days. Traffic changes and rollback deployments remain separate approved operator actions.

Validation, planning, deployment, smoke, and HA workflows retain release evidence for 90 days. Before approval, compare the artifact commit SHA with the reviewed source and managed client artifact. Roll back clients by redeploying the last-known-good managed file and helper; do not remove management policy as a shortcut.
