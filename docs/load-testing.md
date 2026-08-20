# Load testing

The async client and backend use event-loop connections rather than one thread per stream. Maintained plateaus are 500, 1,000, 1,500, 2,000, and 2,500.

```bash
python3 scripts/test/synthetic_sse_backend.py
python3 scripts/test/sse_concurrency_probe.py \
  --url http://127.0.0.1:8088/v1/messages \
  --concurrency 2500 --connect-parallelism 500 \
  --stream-duration 120 --event-interval-ms 1000 --timeout 300
```

The probe reports connection failures, timeouts, client disconnects, 429, 5xx, success, TTFB p50/p95/p99, and stream p95. Use `--synthetic-status`, `--initial-delay-ms`, and `--disconnect-after-events` for failure cases. Raise OS file-descriptor limits and distribute clients/backends when one host saturates; confirm generator CPU/network/event-loop lag before attributing a bottleneck to APIM.

Hold each plateau for at least representative p95 stream duration. Observe APIM and backend connections, capacity, TTFB, error rates, and Foundry quotas. Start with fixed capacity; test optional autoscale separately over its full control-loop duration. Gateway synthetic results do not prove Foundry capacity.

CI runs only small local smoke concurrency. Direct Foundry URLs require `--allow-live-model`; billable live-model load requires explicit customer approval.
