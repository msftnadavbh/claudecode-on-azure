# Troubleshooting

Use this guide after checking the relevant Azure and GitHub evidence. **Prerequisites:** approved operator access to customer-owned Entra, Foundry, networking, and GitHub resources. **Boundary:** do not introduce static credentials, direct Foundry client settings, portal-only APIM edits, or unreviewed traffic changes.

| Symptom | Check | Recovery |
| --- | --- | --- |
| Claude Code cannot authenticate / APIM returns 401 or 403 | Token has configured tenant, audience, `oid`, `tid`, and app role; Azure CLI session and assignment are valid. | Reauthenticate through the approved flow and correct Entra assignment/consent. Use [client auth](client-authentication.md). |
| Public workflow smoke fails | `APIM_BASE_URL` shape is `https://<apim-name>.azure-api.net/claude`; smoke identity has the role. | Inspect workflow evidence and rerun only after correcting Entra or configuration. |
| Private deployment is not releasable | Hosted runners cannot reach private APIM. | Run protected [HA smoke](availability-dr.md) from a labeled in-network runner; retain evidence. |
| 429 responses | Identify per-user RPM, token, concurrency, or Foundry quota pressure. | Tune only from measured capacity/quota evidence. APIM does not retry 429 or trip the circuit breaker. |
| 503 after provider errors | Inspect Foundry/backend 5xx and circuit-breaker telemetry. | Resolve backend cause and allow the one-minute breaker window to close; no POST replay occurs. |
| `/claude/health` succeeds but inference fails | Health is APIM-local only. | Run authenticated count-token and stream smoke, then inspect Foundry/RBAC/preflight. |
| Foundry 401/403 or model error | APIM identity has `Foundry User`; account, endpoint, and all three deployment names match preflight. | Restore role or deployment; customer resolves existing model named values before apply. |
| Client refresh canary fails | Managed settings are active in the canary's launch environment; Azure CLI can refresh. | Start Claude Code from the managed launch environment, reauthenticate, then rerun [canary](claude-code-canary.md). Managed settings do not export values to the parent shell. |
| DNS/failover issue | Separate APIM health from Foundry health; confirm operator traffic change and private/public DNS path. | Follow [availability and DR](availability-dr.md). The workflow observes but never changes traffic. |
| Plan/apply stops on summary or destructive change | Inputs, lock file, state coordinates, or planned changes changed after approval. | Review the change; do not bypass the comparison or deletion/replacement rejection. |

For local tool failures, run `scripts/test/validate.sh`. For a safe synthetic SSE self-test, follow [load testing](load-testing.md); it proves only the local tool path.
