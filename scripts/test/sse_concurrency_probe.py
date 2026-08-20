#!/usr/bin/env python3
import argparse
import json
import threading
import time
import urllib.request


parser = argparse.ArgumentParser(description="Concurrent SSE probe for APIM or synthetic backend")
parser.add_argument("--url", required=True)
parser.add_argument("--concurrency", type=int, default=100)
parser.add_argument("--timeout", type=int, default=60)
args = parser.parse_args()

results = {"ok": 0, "failed": 0}
lock = threading.Lock()


def worker(index: int) -> None:
    body = {
        "model": "claude-sonnet",
        "max_tokens": 128,
        "stream": True,
        "messages": [{"role": "user", "content": f"probe-{index}"}],
    }
    req = urllib.request.Request(
        args.url,
        method="POST",
        headers={"content-type": "application/json"},
        data=json.dumps(body).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            first = resp.readline().decode("utf-8", errors="ignore")
            ok = "event:" in first or "data:" in first
        with lock:
            results["ok" if ok else "failed"] += 1
    except Exception:
        with lock:
            results["failed"] += 1


threads = []
start = time.time()
for i in range(args.concurrency):
    t = threading.Thread(target=worker, args=(i,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()

duration = time.time() - start
print(json.dumps({"concurrency": args.concurrency, "duration_seconds": round(duration, 2), **results}))
