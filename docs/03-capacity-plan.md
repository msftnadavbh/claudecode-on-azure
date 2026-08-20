# Capacity Model and Load Testing

## Concurrency Model

Record the following measured or forecast inputs for each workload class:

- `D`: entitled developers
- `A`: peak active-developer fraction
- `S`: active sessions per active developer
- `W`: concurrent workers/agents per active session
- `Ravg` and `Rp95`: average and p95 stream duration in minutes
- `T`: average think time between streams in minutes
- `B`: observed burst multiplier
- `Iu`, `Iw`, `Ir`, `O`: mean uncached-input, cache-write, cache-read, and output tokens per request, including zero values
- `H`: prompt-cache hit ratio

Primary stream concurrency is:

`C = D * A * S * W`

Cross-check it with Little's Law using measured request starts:

`C_observed = requests_started_per_minute * Ravg`

The higher of `C` and `C_observed`, multiplied by `B`, is the gateway test target. Do not substitute entitled developers for active developers or assume one worker per session.

## Request and Token Demand

For workers that issue a new request after a stream and think-time cycle:

- `RPM = C / (Ravg + T) * B`
- `uncached_input_TPM = RPM * Iu`
- `cache_write_TPM = RPM * Iw`
- `output_TPM = RPM * O`
- `cache_read_TPM = RPM * Ir`
- `cache_hit_RPM = RPM * H`

Keep cache reads, cache writes, uncached input, and output separate because model quota and billing can account for them differently. Calculate each model/deployment independently, then aggregate only where the current Foundry quota page shows that deployments share a quota pool.

## Test Tiers

Run gateway synthetic SSE tests at the following maintained simultaneous-stream plateaus. Each run must hold the target through at least `Rp95`, rather than merely opening that many short requests.

- 500 concurrent streams
- 1000 concurrent streams
- 1500 concurrent streams
- 2000 concurrent streams
- 2500 concurrent streams

## Required Metrics

- Concurrent active streams
- Stream setup success rate
- Time-to-first-byte/time-to-first-token proxy metric
- p95 stream duration
- request-start RPM
- uncached-input, cache-write, cache-read, and output TPM
- prompt-cache hit ratio
- APIM capacity metric
- APIM backend error rate / retry count
- simultaneous client and backend connections
- Foundry 429s by model deployment and quota pool

## Capacity Record and Approval Gate

Production values are intentionally absent from `prod.bicepparam`. Before setting its required environment variables, record:

| Input or result | Interactive | Subagents | Agent teams/batch | Evidence window |
| --- | ---: | ---: | ---: | --- |
| D, A, S, W | TBD | TBD | TBD | Peak business period |
| Ravg, Rp95, T, B | TBD | TBD | TBD | Representative repositories |
| RPM | calculated | calculated | calculated | Formula above |
| Iu, Iw, Ir, O, H | measured | measured | measured | APIM/Foundry usage metrics |
| Required stream plateau | calculated | calculated | calculated | Formula above |
| APIM units at acceptable capacity/error rate | measured | measured | measured | Synthetic SSE test |
| Foundry quota pool and headroom | verified | verified | verified | Foundry quota page/export |

Approve `PER_USER_RATE_LIMIT`, `PER_USER_TOKEN_LIMIT`, and fixed `APIM_DEFAULT_CAPACITY` only after aggregate demand fits measured APIM capacity and the applicable Foundry quota with agreed operational headroom. Start fixed; enable optional autoscale only when sustained APIM utilization justifies its slow control loop. Recalculate after model/version, deployment type, policy, cache behavior, or worker-concurrency changes.

## Two Test Classes

1. Gateway capacity test:
   APIM -> synthetic SSE backend (no model quota dependency)
2. End-to-end model test:
   APIM -> Foundry Claude deployments

Do not run expensive end-to-end high-concurrency tests by default in CI.

Gateway capacity is empirical: do not infer a supported SSE count by multiplying an undocumented connection figure by APIM units. Test every intended SKU, unit count, region, policy revision, payload distribution, `Ravg`, and `Rp95`; scale on sustained capacity/error/latency signals and repeat after changes.

The current APIM classic/v2 service-limits table does not publish a concurrent backend-connection limit. Older support answers are not a sufficient production contract, so confirm the applicable limit with Microsoft for the selected Premium v2 deployment and prove sustained behavior before release. The 2,500-stream plateau is a synthetic gateway test target, not a claim that one Foundry backend authority supports 2,500 production streams.

## Foundry Quota Scope

Verify current quota scope in the target subscription before every capacity approval. Global Standard deployments can share quota at a broader scope than a single resource or region; Data Zone Standard scope differs. A second resource or region therefore does not automatically add quota. Keep model/version deployment names explicit and compare each calculated TPM/RPM dimension with the portal's effective quota.

## First-party references

- [Microsoft Foundry Models quotas and limits](https://learn.microsoft.com/azure/foundry/foundry-models/quotas-limits)
- [Foundry deployment types](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/deployment-types)
- [APIM capacity metric](https://learn.microsoft.com/azure/api-management/api-management-capacity)
- [Configure APIM for server-sent events](https://learn.microsoft.com/azure/api-management/how-to-server-sent-events)
