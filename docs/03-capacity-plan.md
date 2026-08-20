# Capacity Model and Load Testing

## Concurrency Model

Use:

`developers * active_sessions_per_developer * concurrent_workers_per_session`

as primary stream-concurrency input.

## Test Tiers

Run gateway synthetic SSE tests at:

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
- APIM capacity metric
- APIM backend error rate / retry count

## Two Test Classes

1. Gateway capacity test:
   APIM -> synthetic SSE backend (no model quota dependency)
2. End-to-end model test:
   APIM -> Foundry Claude deployments

Do not run expensive end-to-end high-concurrency tests by default in CI.
