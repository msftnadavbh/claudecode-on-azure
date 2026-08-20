#!/usr/bin/env python3
import asyncio
import json
import os

HOST = os.getenv("SSE_HOST", "127.0.0.1")
PORT = int(os.getenv("SSE_PORT", "8088"))
MAX_HEADER_BYTES = 65536


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line = await reader.readline()
        parts = request_line.decode(errors="replace").split()
        if len(parts) != 3:
            return
        method, path, _ = parts
        headers: dict[str, str] = {}
        consumed = len(request_line)
        while line := await reader.readline():
            consumed += len(line)
            if consumed > MAX_HEADER_BYTES:
                return
            if line in {b"\r\n", b"\n"}:
                break
            name, _, value = line.decode(errors="replace").partition(":")
            headers[name.lower()] = value.strip()
        body_length = min(int(headers.get("content-length", "0")), 1_048_576)
        if body_length:
            await reader.readexactly(body_length)

        if method != "POST" or path not in {"/v1/messages", "/v1/messages/count_tokens"}:
            await respond(writer, 404, b'{"error":"not found"}', "application/json")
            return
        if path.endswith("/count_tokens"):
            await respond(writer, 200, b'{"input_tokens":7}', "application/json")
            return

        status = int(headers.get("x-synthetic-status", "200"))
        if status != 200:
            await respond(
                writer,
                status,
                json.dumps({"type": "error", "status": status}).encode(),
                "application/json",
                extra_headers={"Retry-After": "1"} if status == 429 else None,
            )
            return

        duration = max(0.0, float(headers.get("x-synthetic-duration-seconds", "6")))
        cadence = max(0.001, int(headers.get("x-synthetic-event-interval-ms", "200")) / 1000)
        initial_delay = max(0.0, int(headers.get("x-synthetic-initial-delay-ms", "0")) / 1000)
        event_count = max(1, round(duration / cadence))
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
            b"Cache-Control: no-cache\r\nConnection: close\r\n\r\n"
        )
        await writer.drain()
        await asyncio.sleep(initial_delay)
        writer.write(b'event: message_start\ndata: {"type":"message_start"}\n\n')
        await writer.drain()
        for index in range(event_count):
            payload = {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": f"token-{index}"},
            }
            writer.write(
                f"event: content_block_delta\ndata: {json.dumps(payload)}\n\n".encode()
            )
            await writer.drain()
            await asyncio.sleep(cadence)
        writer.write(b'event: message_stop\ndata: {"type":"message_stop"}\n\n')
        await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError, ValueError):
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def respond(
    writer: asyncio.StreamWriter,
    status: int,
    body: bytes,
    content_type: str,
    extra_headers: dict[str, str] | None = None,
) -> None:
    reasons = {200: "OK", 404: "Not Found", 429: "Too Many Requests", 500: "Internal Server Error", 503: "Service Unavailable"}
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
        "Connection": "close",
        **(extra_headers or {}),
    }
    encoded_headers = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
    writer.write(
        f"HTTP/1.1 {status} {reasons.get(status, 'Status')}\r\n{encoded_headers}\r\n".encode()
        + body
    )
    await writer.drain()


async def main() -> None:
    server = await asyncio.start_server(handle, HOST, PORT, backlog=4096)
    print(f"Synthetic async SSE backend listening on http://{HOST}:{PORT}/v1/messages")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
