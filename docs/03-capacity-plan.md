# Capacity and load planning

Measure capacity before setting APIM limits or approving rollout. You need representative workload data, Foundry quota visibility, and authority to run approved tests. No repository default proves APIM or Foundry capacity.

## Model demand

Record entitled developers (`D`), peak active fraction (`A`), sessions (`S`), workers (`W`), stream duration (`Ravg`/`Rp95`), think time (`T`), burst multiplier (`B`), and uncached input/cache write/cache read/output tokens (`Iu`/`Iw`/`Ir`/`O`) with cache hit ratio (`H`).

`C = D * A * S * W` is the starting stream-concurrency estimate. Cross-check it with `requests_started_per_minute * Ravg`; use the higher value times `B` as the test target. Estimate `RPM = C / (Ravg + T) * B`, then calculate each token dimension per model deployment. Confirm the effective Foundry quota pool rather than assuming a region or account adds quota.

## Approval record

| Approve only after measuring | Evidence |
| --- | --- |
| Fixed `APIM_DEFAULT_CAPACITY` | Sustained APIM capacity, latency, connection, and error results for selected SKU/region/policy. |
| Per-user RPM and messages TPM | Representative user/workload demand and fairness policy. |
| Per-user and aggregate concurrency | Measured headroom with `per-user < aggregate < 2048` per gateway. |
| Foundry quota and model pinning | Deployment/version/type and effective RPM/TPM pool/headroom. |

Use the maintained 500, 1,000, 1,500, and 2,000-stream plateaus; 2,500 is deliberate overload rejection only. Hold each target for at least representative `Rp95`. A local synthetic backend tests the probe path, while APIM-to-synthetic measures gateway behavior and APIM-to-Foundry is a separate, approved billable test. See [load testing](load-testing.md).
