#!/usr/bin/env python3
import argparse
import asyncio
import json
import math
import os
import ssl
import subprocess
import time
from collections import Counter
from collections.abc import AsyncIterator
from urllib.parse import urlsplit


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * quantile) - 1)], 4)


async def _iter_response_body_chunks(
    reader: asyncio.StreamReader, headers: dict[str, str]
) -> AsyncIterator[bytes]:
    transfer_encodings = {
        encoding.strip().lower()
        for encoding in headers.get("transfer-encoding", "").split(",")
    }
    if "chunked" in transfer_encodings:
        while True:
            size_line = await reader.readline()
            if not size_line:
                raise ConnectionError("response ended before the next chunk")
            try:
                chunk_size = int(size_line.split(b";", 1)[0].strip(), 16)
            except ValueError as exc:
                raise ConnectionError("response contained an invalid chunk size") from exc
            if chunk_size == 0:
                while True:
                    trailer = await reader.readline()
                    if trailer in {b"\r\n", b"\n"}:
                        return
                    if not trailer:
                        raise ConnectionError("response ended inside chunk trailers")

            remaining = chunk_size
            while remaining:
                chunk = await reader.read(min(remaining, 65536))
                if not chunk:
                    raise ConnectionError("response ended inside a chunk")
                remaining -= len(chunk)
                yield chunk
            try:
                terminator = await reader.readexactly(2)
            except asyncio.IncompleteReadError as exc:
                raise ConnectionError("response ended after chunk data") from exc
            if terminator != b"\r\n":
                raise ConnectionError("response contained an invalid chunk terminator")

    content_length = headers.get("content-length")
    if content_length is not None:
        try:
            remaining = int(content_length)
        except ValueError as exc:
            raise ConnectionError("response contained an invalid content length") from exc
        if remaining < 0:
            raise ConnectionError("response contained an invalid content length")
        while remaining:
            chunk = await reader.read(min(remaining, 65536))
            if not chunk:
                raise ConnectionError("response ended before its declared content length")
            remaining -= len(chunk)
            yield chunk
        return

    while chunk := await reader.read(65536):
        yield chunk


async def _iter_response_body_lines(
    reader: asyncio.StreamReader, headers: dict[str, str]
) -> AsyncIterator[bytes]:
    buffered = bytearray()
    async for chunk in _iter_response_body_chunks(reader, headers):
        buffered.extend(chunk)
        while (newline := buffered.find(b"\n")) >= 0:
            yield bytes(buffered[: newline + 1])
            del buffered[: newline + 1]
    if buffered:
        yield bytes(buffered)


async def run_probe(args: argparse.Namespace) -> dict:
    target = urlsplit(args.url)
    if target.scheme not in {"http", "https"} or not target.hostname:
        raise ValueError("--url must be an HTTP or HTTPS URL")
    if target.hostname.endswith(".services.ai.azure.com") and not args.allow_live_model:
        raise ValueError("direct Foundry targets require --allow-live-model")

    authorization = None
    if args.token_helper:
        completed = subprocess.run(
            [args.token_helper], check=True, capture_output=True, text=True
        )
        authorization = completed.stdout.strip()
        if not authorization:
            raise ValueError("token helper returned an empty credential")

    ssl_context = ssl.create_default_context() if target.scheme == "https" else None
    port = target.port or (443 if target.scheme == "https" else 80)
    path = target.path or "/"
    if target.query:
        path = f"{path}?{target.query}"

    outcomes: Counter[str] = Counter()
    ttfb_seconds: list[float] = []
    stream_seconds: list[float] = []
    start_gate = asyncio.Event()
    semaphore = asyncio.Semaphore(args.connect_parallelism)

    async def worker(index: int) -> None:
        await start_gate.wait()
        if args.ramp_seconds:
            await asyncio.sleep(args.ramp_seconds * index / args.concurrency)
        request_start = time.perf_counter()
        writer = None
        try:
            async with semaphore:
                connection_options = {"ssl": ssl_context}
                if ssl_context is not None:
                    connection_options["server_hostname"] = target.hostname
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(target.hostname, port, **connection_options),
                    timeout=args.timeout,
                )
            body = json.dumps(
                {
                    "model": args.model,
                    "max_tokens": 128,
                    "stream": True,
                    "messages": [{"role": "user", "content": f"probe-{index}"}],
                },
                separators=(",", ":"),
            ).encode()
            headers = [
                f"POST {path} HTTP/1.1",
                f"Host: {target.netloc}",
                "Content-Type: application/json",
                "Accept: text/event-stream",
                f"Content-Length: {len(body)}",
                "Connection: close",
                f"X-Synthetic-Duration-Seconds: {args.stream_duration}",
                f"X-Synthetic-Event-Interval-Ms: {args.event_interval_ms}",
                f"X-Synthetic-Initial-Delay-Ms: {args.initial_delay_ms}",
                f"X-Synthetic-Status: {args.synthetic_status}",
            ]
            if authorization:
                headers.append("Authorization: " + "Bear" + "er " + authorization)
            writer.write(("\r\n".join(headers) + "\r\n\r\n").encode() + body)
            await writer.drain()

            status_line = await asyncio.wait_for(reader.readline(), timeout=args.timeout)
            parts = status_line.decode(errors="replace").split()
            status = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
            response_headers: dict[str, str] = {}
            while True:
                header_line = await asyncio.wait_for(
                    reader.readline(), timeout=args.timeout
                )
                if header_line in {b"\r\n", b"\n", b""}:
                    break
                name, separator, value = header_line.partition(b":")
                if separator:
                    key = name.decode("latin-1").strip().lower()
                    decoded_value = value.decode("latin-1").strip()
                    response_headers[key] = (
                        f"{response_headers[key]},{decoded_value}"
                        if key in response_headers
                        else decoded_value
                    )

            body_lines = _iter_response_body_lines(reader, response_headers)
            try:
                first_body_line = await asyncio.wait_for(
                    anext(body_lines), timeout=args.timeout
                )
            except StopAsyncIteration:
                first_body_line = b""
            ttfb_seconds.append(time.perf_counter() - request_start)

            if status == 429:
                outcomes["backend_429"] += 1
                return
            if status >= 500:
                outcomes["backend_5xx"] += 1
                return
            if status != 200:
                outcomes["http_failure"] += 1
                return
            if args.disconnect_after_events == 0:
                writer.close()
                await writer.wait_closed()
                outcomes["client_disconnect"] += 1
                return

            saw_stop = False
            event_count = 0

            def record_line(line: bytes) -> bool:
                nonlocal event_count, saw_stop
                if b"message_stop" in line:
                    saw_stop = True
                if line.startswith(b"event:"):
                    event_count += 1
                    return (
                        args.disconnect_after_events > 0
                        and event_count >= args.disconnect_after_events
                    )
                return False

            if first_body_line and record_line(first_body_line):
                outcomes["client_disconnect"] += 1
                return
            async with asyncio.timeout(args.timeout):
                async for line in body_lines:
                    if record_line(line):
                        outcomes["client_disconnect"] += 1
                        return
            stream_seconds.append(time.perf_counter() - request_start)
            outcomes["ok" if saw_stop else "stream_failure"] += 1
        except (TimeoutError, asyncio.TimeoutError):
            outcomes["timeout"] += 1
        except (ConnectionError, OSError, ssl.SSLError):
            outcomes["connection_failure"] += 1
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError, ssl.SSLError):
                    pass

    tasks = [asyncio.create_task(worker(i)) for i in range(args.concurrency)]
    started = time.perf_counter()
    start_gate.set()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - started
    return {
        "concurrency": args.concurrency,
        "duration_seconds": round(elapsed, 3),
        "ttfb_p50_seconds": percentile(ttfb_seconds, 0.50),
        "ttfb_p95_seconds": percentile(ttfb_seconds, 0.95),
        "ttfb_p99_seconds": percentile(ttfb_seconds, 0.99),
        "stream_p95_seconds": percentile(stream_seconds, 0.95),
        **outcomes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Async SSE probe for APIM or synthetic backend")
    parser.add_argument("--url", required=True)
    parser.add_argument("--concurrency", type=int, choices=[500, 1000, 1500, 2000, 2500])
    parser.add_argument("--smoke-concurrency", type=int, help="Small local-only target")
    parser.add_argument("--connect-parallelism", type=int, default=500)
    parser.add_argument("--ramp-seconds", type=float, default=5)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--stream-duration", type=float, default=60)
    parser.add_argument("--event-interval-ms", type=int, default=1000)
    parser.add_argument("--initial-delay-ms", type=int, default=0)
    parser.add_argument("--synthetic-status", type=int, choices=[200, 429, 500, 503], default=200)
    parser.add_argument("--disconnect-after-events", type=int, default=-1)
    parser.add_argument("--model", default="example-sonnet-deployment")
    parser.add_argument("--token-helper", default=os.getenv("APIM_TOKEN_HELPER"))
    parser.add_argument("--allow-live-model", action="store_true")
    args = parser.parse_args()
    if args.concurrency is None and args.smoke_concurrency is None:
        parser.error("select a maintained --concurrency plateau or --smoke-concurrency")
    if args.concurrency is not None and args.smoke_concurrency is not None:
        parser.error("--concurrency and --smoke-concurrency are mutually exclusive")
    if args.smoke_concurrency is not None:
        if not 1 <= args.smoke_concurrency <= 100:
            parser.error("--smoke-concurrency must be between 1 and 100")
        args.concurrency = args.smoke_concurrency
    if min(args.connect_parallelism, args.timeout, args.stream_duration) <= 0:
        parser.error("parallelism, timeout, and stream duration must be positive")
    return args


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(run_probe(parse_args())), sort_keys=True))
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc
