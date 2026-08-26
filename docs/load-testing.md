# Load testing

**Purpose:** validate the local probe and guide approved gateway/load runs. **Prerequisites:** Python 3 and, for APIM/Foundry tests, customer approval and target access. **Boundary:** a local synthetic test proves neither APIM nor Foundry capacity.

## Safe local tool self-test

Start the synthetic backend in one terminal:

```bash
python3 scripts/test/synthetic_sse_backend.py
```

In another terminal, expect all streams to succeed:

```bash
python3 scripts/test/sse_concurrency_probe.py \
  --url http://127.0.0.1:8088/v1/messages \
  --smoke-concurrency 2 --stream-duration 0.1 --event-interval-ms 50 --timeout 10
```

To test the probe's intentional 429 handling only, use a synthetic response:

```bash
python3 scripts/test/sse_concurrency_probe.py \
  --url http://127.0.0.1:8088/v1/messages \
  --smoke-concurrency 2 --synthetic-status 429 --min-ok 0 --max-ok 0 --require-429
```

## Approved capacity runs

Use the maintained 500/1,000/1,500/2,000 simultaneous-stream plateaus and hold each for representative p95 duration. Use 2,500 only as an overload-rejection test. Measure setup success, TTFB, stream duration, request rate, APIM capacity/error signals, connections, and Foundry 429/quota by deployment. Direct Foundry URLs require `--allow-live-model` and are billable; approve them separately. See [capacity and load planning](03-capacity-plan.md).
