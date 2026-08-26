# Load testing

The async client and backend use event-loop connections rather than one thread per stream. APIM v2 supports 2,048 concurrent backend connections per HTTP authority; configured admission must remain below that limit. The 2,500 target is an overload-rejection test, not a successful-stream target.

```bash
# Terminal 1
python3 scripts/test/synthetic_sse_backend.py
```

In a separate terminal, run:

```bash
# Terminal 2
python3 scripts/test/sse_concurrency_probe.py \
  --url http://127.0.0.1:8088/v1/messages \
  --concurrency 2500 --connect-parallelism 500 \
  --stream-duration 120 --event-interval-ms 1000 --timeout 300 \
  --require-429
```

The probe reports connection failures, timeouts, client disconnects, 429, 5xx, success, TTFB p50/p95/p99, and stream p95. Use `--synthetic-status`, `--initial-delay-ms`, and `--disconnect-after-events` for failure cases. Raise OS file-descriptor limits and distribute clients/backends when one host saturates; confirm generator CPU/network/event-loop lag before attributing a bottleneck to APIM.

Hold each plateau for at least representative p95 stream duration. Observe APIM and backend connections, capacity, TTFB, error rates, and Foundry quotas. The supported baseline uses fixed measured capacity. Gateway synthetic results do not prove Foundry capacity.

CI runs only small local smoke concurrency. Direct Foundry URLs require `--allow-live-model`; billable live-model load requires explicit customer approval.

Use repeated `--token-helper` values to exercise aggregate admission across identities. By default every stream must succeed; use `--min-ok`, `--max-ok`, and `--require-429` to define expected overload results.
