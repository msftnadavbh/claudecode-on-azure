#!/usr/bin/env python3
import argparse
import asyncio
import subprocess
import unittest
from unittest.mock import patch, AsyncMock, Mock

import sse_concurrency_probe as probe
from sse_concurrency_probe import accepted, run_probe


def arguments(**changes):
    return argparse.Namespace(**dict(dict(url="http://127.0.0.1:8088/v1/messages", token_helper=None,
        allow_live_model=False, connect_parallelism=1, ramp_seconds=0, concurrency=1, timeout=2,
        model="test-sonnet", stream_duration=0.01, event_interval_ms=1, initial_delay_ms=0,
        synthetic_status=200, disconnect_after_events=-1), **changes))


START = b'event: message_start\ndata: {"type":"message_start"}\n\n'
STOP = b'event: message_stop\ndata: {"type":"message_stop"}\n\n'


class SseConcurrencyProbeTests(unittest.IsolatedAsyncioTestCase):
    def test_acceptance_requires_all_success_without_expectations(self) -> None:
        args = argparse.Namespace(concurrency=2, min_ok=None, max_ok=None, require_429=False)
        self.assertTrue(accepted({"ok": 2}, args))
        self.assertFalse(accepted({"http_429": 2}, args))
        self.assertFalse(accepted({"ok": 1, "client_disconnect": 1}, args))

    def test_acceptance_allows_expected_overload_but_not_disconnects(self) -> None:
        args = argparse.Namespace(concurrency=2, min_ok=0, max_ok=0, require_429=True)
        self.assertTrue(accepted({"http_429": 2}, args))
        self.assertFalse(accepted({"http_429": 1}, args))
        self.assertFalse(accepted({"http_429": 1, "client_disconnect": 1}, args))

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
                    START,
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
        args = arguments(url=f"http://127.0.0.1:{port}/v1/messages")
        try:
            result = await run_probe(args)
        finally:
            server.close()
            await server.wait_closed()

        self.assertEqual(result.get("ok"), 1)
        self.assertNotIn("stream_failure", result)

    async def test_rejection_precedes_helper_and_connect(self):
        cases = [dict(url=url) for url in (
            "http://localhost/v1/messages", "http://remote.example/v1/messages", "https://remote.example/v1/messages",
            "http://127.0.0.1:bad/", "http://127.0.0.1:0/", "http://127.0.0.1:65536/", "http://127.0.0.1:/",
            "http://user@127.0.0.1/", "http://127.0.0.1/?", "http://127.0.0.1/#",
            "http://127.0.0.1/\r\nInjected:yes", "http://127.0.0.1/\t")]
        cases += [dict(token_helper=["/helper"]), dict(url="http://remote.example/", allow_live_model=True),
                  dict(timeout=float("nan")), dict(ramp_seconds=float("inf")), dict(initial_delay_ms=-1),
                  dict(event_interval_ms=0), dict(concurrency=0), dict(disconnect_after_events=-2)]
        for case in cases:
            with self.subTest(case=case), patch.object(probe, "token_from_helper") as helper, \
                 patch.object(asyncio, "open_connection") as connect:
                with self.assertRaises(ValueError):
                    await run_probe(arguments(**case))
                helper.assert_not_called()
                connect.assert_not_called()

    async def test_approved_mocked_https_and_helper_failures(self):
        args = arguments(url="https://gateway.example/claude/v1/messages", allow_live_model=True, token_helper=["/helper"])
        reader = asyncio.StreamReader()
        reader.feed_data(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n" + START + STOP)
        reader.feed_eof()
        writer = Mock(drain=AsyncMock(), wait_closed=AsyncMock())
        with patch.object(probe, "token_from_helper", return_value="fake-token"), \
             patch.object(asyncio, "open_connection", new=AsyncMock(return_value=(reader, writer))) as connect:
            result = await run_probe(args)
        self.assertEqual(result.get("ok"), 1)
        self.assertIsNotNone(connect.call_args.kwargs["ssl"])
        self.assertEqual(connect.call_args.kwargs["server_hostname"], "gateway.example")
        self.assertIn(b"anthropic-version: 2023-06-01", writer.write.call_args.args[0])
        for output in (b"secret\ninjected", b"null", b" secret ", b"secret\n\n"):
            with patch("endpoint_smoke_matrix.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output)), \
                 patch.object(asyncio, "open_connection") as connect:
                with self.assertRaisesRegex(ValueError, "^credential_helper_failed$"):
                    await run_probe(args)
                connect.assert_not_called()
        with patch("endpoint_smoke_matrix.subprocess.run", side_effect=subprocess.TimeoutExpired("secret", 1, output=b"secret")), \
             patch.object(asyncio, "open_connection") as connect:
            with self.assertRaisesRegex(ValueError, "^credential_helper_failed$"):
                await run_probe(args)
            connect.assert_not_called()

    async def test_incomplete_records_and_http_framing_fail(self):
        cases = [START, STOP + START, START + STOP[:-1],
                 START + b'event: content_block_delta\ndata: {"type":"content_block_delta","text":"message_stop"}\n\n',
                 START + b'event: error\ndata: {"type":"error"}\n\n' + STOP]
        for body in cases:
            reader = asyncio.StreamReader()
            reader.feed_data(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n" + body)
            reader.feed_eof()
            with patch.object(asyncio, "open_connection", new=AsyncMock(return_value=(reader, Mock(drain=AsyncMock(), wait_closed=AsyncMock())))):
                result = await run_probe(arguments())
            self.assertEqual(result.get("stream_failure"), 1)
        for headers, body in [(b"Content-Type: text/event-streaming\r\n", START + STOP),
                              (b"Content-Type: text/event-stream\r\nContent-Length: 9999\r\n", START + STOP),
                              (b"Content-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n", f"{len(START + STOP):x}\r\n".encode() + START + STOP + b"\r\n")]:
            reader = asyncio.StreamReader()
            reader.feed_data(b"HTTP/1.1 200 OK\r\n" + headers + b"\r\n" + body)
            reader.feed_eof()
            with patch.object(asyncio, "open_connection", new=AsyncMock(return_value=(reader, Mock(drain=AsyncMock(), wait_closed=AsyncMock())))):
                result = await run_probe(arguments())
            self.assertNotIn("ok", result)

    async def test_delayed_first_event_observed_before_completion_and_buffered_control(self):
        for buffered in (False, True):
            first_seen, release, headers_sent = asyncio.Event(), asyncio.Event(), asyncio.Event()
            real_feed = probe.SSERecords.feed
            def observe(records, line):
                event = real_feed(records, line)
                if event == "message_start":
                    first_seen.set()
                return event
            async def handle(reader, writer):
                await reader.readuntil(b"\r\n\r\n")
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n")
                await writer.drain()
                headers_sent.set()
                await asyncio.sleep(0.05)
                if not buffered:
                    writer.write(START)
                    await writer.drain()
                await release.wait()
                writer.write((START if buffered else b"") + STOP)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            server = await asyncio.start_server(handle, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            try:
                with patch.object(probe.SSERecords, "feed", observe):
                    task = asyncio.create_task(run_probe(arguments(url=f"http://127.0.0.1:{port}/v1/messages")))
                    await asyncio.wait_for(headers_sent.wait(), 1)
                    if buffered:
                        await asyncio.sleep(0.1)
                        self.assertFalse(first_seen.is_set())
                    else:
                        await asyncio.wait_for(first_seen.wait(), 1)
                        self.assertFalse(task.done())
                    release.set()
                    result = await task
                self.assertEqual(result.get("ok"), 1)
                self.assertGreater(result["first_event_p50_seconds"], result["header_p50_seconds"])
            finally:
                release.set()
                server.close()
                await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
