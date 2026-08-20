#!/usr/bin/env python3
import argparse
import asyncio
import unittest

from sse_concurrency_probe import run_probe


class SseConcurrencyProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_decodes_chunked_lines_split_across_chunks(self) -> None:
        async def handle(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                await reader.readline()
                content_length = 0
                while line := await reader.readline():
                    if line in {b"\r\n", b"\n"}:
                        break
                    name, _, value = line.partition(b":")
                    if name.lower() == b"content-length":
                        content_length = int(value)
                if content_length:
                    await reader.readexactly(content_length)

                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/event-stream\r\n"
                    b"Transfer-Encoding: Chunked\r\n"
                    b"Connection: close\r\n\r\n"
                )
                for chunk in (
                    b"event: message_",
                    b"stop\n",
                    b'data: {"type":"message_stop"}\n\n',
                ):
                    writer.write(f"{len(chunk):x}\r\n".encode())
                    writer.write(chunk + b"\r\n")
                writer.write(b"0\r\n\r\n")
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        args = argparse.Namespace(
            url=f"http://127.0.0.1:{port}/v1/messages",
            token_helper=None,
            allow_live_model=False,
            connect_parallelism=1,
            ramp_seconds=0,
            concurrency=1,
            timeout=2,
            model="test-sonnet",
            stream_duration=0.01,
            event_interval_ms=1,
            initial_delay_ms=0,
            synthetic_status=200,
            disconnect_after_events=-1,
        )
        try:
            result = await run_probe(args)
        finally:
            server.close()
            await server.wait_closed()

        self.assertEqual(result.get("ok"), 1)
        self.assertNotIn("stream_failure", result)


if __name__ == "__main__":
    unittest.main()
