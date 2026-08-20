# Operations and rollback

| Failure | Detection / user symptom | Automatic mitigation | Operator action / recovery |
| --- | --- | --- | --- |
| User token expires | helper/auth error or 401 | helper asks MSAL for a current token | Reauthenticate Azure CLI; verify assignment/CA |
| Helper/Azure CLI unavailable | Claude request cannot start | none | Install/sign in; never substitute shared credentials |
| APIM MI token or RBAC failure | backend 401/403, users see provider error | none | Restore identity and `Cognitive Services User`; redeploy RBAC |
| Foundry 429/500/503 | alerts, streamed call fails | circuit opens; `Retry-After` honored | Check quota/health; client retries; no APIM POST replay |
| Primary region/DNS failure | Traffic Manager health degraded | priority failover | Run secondary smoke; repair primary; manual failback |
| APIM saturation/connections | CPU/capacity/latency alert | autoscale to configured maximum | Reduce load, raise validated max, or add capacity |
| Client disconnect | incomplete stream traces | backend connection closes | No operator action unless rate spikes |
| Circuit open | 429/503 spike after backend failures | one-minute trip window | Resolve backend cause and observe closure |
| Telemetry unavailable/delayed | ingestion gap | inference continues | Repair diagnostic destination; do not enable bodies |
| Agent fan-out/morning surge | per-user 429, capacity/quota pressure | per-user fairness/autoscale | Validate entitlement, limits, and aggregate quota |
| Deployment renamed/removed | backend model errors | none | Restore pinned deployment or controlled settings update |
| Claude Code alias behavior changes | wrong/failed model selection | pinned deployment env values | Halt rollout; regression-test and pin client version |

## Deployment rollback

Every deployment uses Bicep and API revision `1`. Before production approval, retain the previous successful commit and what-if. To roll back, dispatch the workflow at that commit (or redeploy its template), review what-if for destructive changes, deploy, and smoke both regions. Do not roll back or mutate customer-owned Foundry deployments through this repository.

For a policy-only incident, redeploy the last known-good commit rather than editing APIM in the portal. For regional incidents, keep the failed endpoint disabled until health and authenticated smoke pass.
