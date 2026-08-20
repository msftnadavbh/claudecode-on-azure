#!/usr/bin/env python3
import argparse
import json
import math
import os
import subprocess
import threading
import time
import urllib.request


parser = argparse.ArgumentParser(description="Concurrent SSE probe for APIM or synthetic backend")
parser.add_argument("--url", required=True)
parser.add_argument("--concurrency", type=int, default=100)
parser.add_argument("--timeout", type=int, default=60)
parser.add_argument(
    "--token-helper",
    default=os.getenv("APIM_TOKEN_HELPER"),
    help="Executable that prints an Entra token; can also be set with APIM_TOKEN_HELPER",
)
args = parser.parse_args()
if args.concurrency < 1:
    parser.error("--concurrency must be at least 1")
if args.timeout < 1:
    parser.error("--timeout must be at least 1")

results = {"ok": 0, "failed": 0}
ttfb_seconds = []
stream_seconds = []
lock = threading.Lock()
start_gate = threading.Event()
authorization = None
if args.token_helper:
    completed = subprocess.run(
        [args.token_helper],
        check=True,
        capture_output=True,
        text=True,
    )
    token = completed.stdout.strip()
    if not token:
        parser.error("token helper returned an empty token")
    authorization = f'{"Bear" + "er"} {token}'


def worker(index: int) -> None:
    start_gate.wait()
    request_start = time.perf_counter()
    body = {
        "model": "claude-sonnet",
        "max_tokens": 128,
        "stream": True,
        "messages": [{"role": "user", "content": f"probe-{index}"}],
    }
    headers = {"content-type": "application/json"}
    if authorization:
        headers["Authorization"] = authorization

    req = urllib.request.Request(
        args.url,
        method="POST",
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            first = resp.readline().decode("utf-8", errors="ignore")
            ttfb = time.perf_counter() - request_start
            saw_stop = any(
                "message_stop" in line.decode("utf-8", errors="ignore")
                for line in resp
            )
            ok = ("event:" in first or "data:" in first) and saw_stop
            stream_duration = time.perf_counter() - request_start
        with lock:
            results["ok" if ok else "failed"] += 1
            if ok:
                ttfb_seconds.append(ttfb)
                stream_seconds.append(stream_duration)
    except Exception:
        with lock:
            results["failed"] += 1


threads = []
for i in range(args.concurrency):
    t = threading.Thread(target=worker, args=(i,))
    t.start()
    threads.append(t)

start = time.time()
start_gate.set()
for t in threads:
    t.join()


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)]


duration = time.time() - start
summary = {
    "concurrency": args.concurrency,
    "duration_seconds": round(duration, 3),
    "ttfb_p95_seconds": percentile(ttfb_seconds, 0.95),
    "stream_p95_seconds": percentile(stream_seconds, 0.95),
    **results,
}
print(json.dumps(summary))
