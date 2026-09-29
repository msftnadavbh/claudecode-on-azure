# Load testing

Use this page to validate the local probe and run approved gateway load tests. You need Python 3 and, for APIM or Foundry tests, approval and target access. A local synthetic test proves neither APIM nor Foundry capacity.

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

Use the maintained 500/1,000/1,500/2,000 simultaneous-stream plateaus and hold each for representative p95 duration. Use 2,500 only as an overload-rejection test. Measure setup success, first-event latency, header latency, stream duration, request rate, APIM capacity/error signals, connections, and Foundry 429/quota by deployment. See [capacity and load planning](03-capacity-plan.md).

Only unauthenticated HTTP to a literal loopback IP is allowed without explicit approval. Every other target requires HTTPS **and** `--allow-live-model`, including remote APIM and remote synthetic targets; any credential helper requires HTTPS even on loopback. `--smoke-concurrency` limits count, not destination safety or billing. Unset `APIM_TOKEN_HELPER` for unauthenticated local self-tests. Helpers are noninteractive, bounded to at most 30 seconds, and return a single raw token; malformed/failing output produces a fixed error without credential disclosure. No redirects, TLS bypass, or request retries are used. Approve destination, identities, cost, concurrency and duration before opting in.

Success requires HTTP 200, exact `text/event-stream` media type, complete SSE records with `message_start` before `message_stop`, and no error before completion. EOF before completion, truncated framing, and a `message_stop` substring in content do not pass. `header_*` measures header arrival; `first_event_*` measures the first complete event. Legacy probe `ttfb_*` fields now alias first-event timing. Endpoint matrix `ttfb_seconds` remains header timing and `first_event_seconds` is separate. Delayed and buffered local tests verify observation timing, not a production latency SLO or real gateway unbuffered delivery.

Probe `--timeout` bounds connection setup and individual header reads; **after response headers**, a response-body watchdog bounds the entire stream. It is not a universal end-to-end wall-clock deadline: DNS/connect and header phases retain their existing limits.

The tested SSE framing baseline is LF and CRLF, including lines split across transport chunks. CR-only framing support is deferred and fails closed; this validator is not a general-purpose implementation of every SSE line-ending variant.
