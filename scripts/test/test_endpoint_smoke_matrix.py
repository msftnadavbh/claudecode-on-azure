#!/usr/bin/env python3
import argparse
import io
import json
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch, Mock


sys.path.insert(0, str(Path(__file__).parent))
import endpoint_smoke_matrix as smoke


class Response:
    def __init__(self, status, body=b"", content_type="application/json"):
        self.status, self.body, self.content_type = status, body, content_type
        self.lines = iter(body.splitlines(keepends=True))

    def read(self): return self.body
    def readline(self): return next(self.lines, b"")
    def getheader(self, name): return self.content_type if name.lower() == "content-type" else None
    def close(self): pass


class Connection:
    health_status = 200

    def __init__(self, *_args, **_kwargs): self.path = ""
    def connect(self): pass
    sock = None
    def request(self, _method, path, **_kwargs): self.path = path
    def getresponse(self):
        if self.path.endswith("/health"):
            return Response(self.health_status, b"healthy")
        if self.path.endswith("count_tokens"):
            return Response(200, b'{"input_tokens":1}') if self.authorized else Response(401)
        if self.path.endswith("messages"):
            return Response(401) if not self.authorized else Response(
                200, b'event: message_start\ndata: {"type":"message_start"}\n\nevent: message_stop\ndata: {"type":"message_stop"}\n\n', "text/event-stream"
            )
        raise AssertionError(self.path)
    def close(self): pass


class EndpointSmokeMatrixTests(unittest.TestCase):
    def run_smoke(self, health_status=200):
        Connection.health_status = health_status
        original_request = Connection.request
        def request(self, method, path, **kwargs):
            self.authorized = "Authorization" in kwargs["headers"]
            original_request(self, method, path, **kwargs)
        args = argparse.Namespace(
            endpoints=[("primary", "https://gateway.example/claude")],
            models=[("opus", "pinned-opus"), ("sonnet", "pinned-sonnet"), ("haiku", "pinned-haiku")],
            token_helper="helper", timeout=1, phase="readiness",
        )
        helper = subprocess.CompletedProcess(["helper"], 0, stdout=b"token\n")
        with patch.object(smoke.socket, "getaddrinfo", return_value=[(None, None, None, None, ("203.0.113.1", 443))]), \
             patch.object(smoke.http.client, "HTTPSConnection", Connection), \
             patch.object(Connection, "request", request), \
             patch.object(smoke.subprocess, "run", return_value=helper) as run:
            result = smoke.run(args)
        self.assertEqual(run.call_count, 1)
        return result

    def test_success(self):
        result = self.run_smoke()
        endpoint = result["endpoints"][0]
        self.assertTrue(result["ok"])
        self.assertEqual(endpoint["dns_addresses"], ["203.0.113.1"])
        self.assertEqual(endpoint["checks"]["health"]["label"], "gateway-local")
        self.assertEqual(set(endpoint["checks"]["count_tokens"]), {"opus", "sonnet", "haiku"})
        self.assertIsNone(endpoint["checks"]["messages_sse"]["error"])
        for operation in ("messages", "count_tokens"):
            self.assertEqual(endpoint["checks"][f"unauthenticated_{operation}"]["status"], 401)
        self.assertIn("first_event_seconds", endpoint["checks"]["messages_sse"])
        self.assertEqual(result["negative_auth_cases"], [])

    def test_endpoint_failure(self):
        result = self.run_smoke(health_status=503)
        self.assertFalse(result["ok"])
        self.assertEqual(result["endpoints"][0]["checks"]["health"]["error"], "unexpected_status")

    def test_stream_records_and_framing(self):
        start = b'event: message_start\ndata: {"type":"message_start"}\n\n'
        stop = b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
        for body, content_type, status, ok in [
            (start + stop, "text/event-stream; charset=utf-8", 200, True),
            ((start + stop).replace(b"\n", b"\r\n"), "text/event-stream", 200, True),
            ((start + stop).replace(b"\n", b"\r"), "text/event-stream", 200, False),
            (stop + start, "text/event-stream", 200, False),
            (start + stop[:-1], "text/event-stream", 200, False),
            (start + b'data: {"text":"message_stop"}\n\n', "text/event-stream", 200, False),
            (start + b'event: error\ndata: {"type":"error"}\n\n' + stop, "text/event-stream", 200, False),
            (start + stop, "text/event-streaming", 200, False),
            (start + stop, "text/event-stream", 201, False),
        ]:
            response = Response(status, body, content_type)
            with self.subTest(body=body, content_type=content_type, status=status), patch.object(smoke, "request", return_value=(Mock(), response, smoke.check(status=status, ttfb=0))):
                self.assertEqual(smoke.stream_check("https://gateway/claude", "{}", {}, 1)["error"] is None, ok)

    def test_negative_cases_are_opt_in_and_safe(self):
        args = ["--endpoint", "primary=https://gateway.example/claude", "--token-helper", "/positive",
                "--model", "opus=one", "--model", "sonnet=one", "--model", "haiku=one",
                "--negative-case", "wrong-tenant=401=/negative"]
        with patch.object(smoke, "run") as run, redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            smoke.main(args)
        run.assert_not_called()
        for case in ("label=400=/helper", "label=401=relative", "bad label=401=/helper", "x\n=401=/helper"):
            with self.assertRaises(ValueError):
                smoke.negative_case(case)

    def test_negative_matrix_one_request_per_operation_without_body_logging(self):
        args = argparse.Namespace(endpoints=[("primary", "https://gateway.example/claude")],
            models=[("opus", "one"), ("sonnet", "one"), ("haiku", "one")],
            token_helper="/positive", timeout=1, phase="readiness", allow_negative_auth=True,
            negative_cases=[("wrong-tenant", 401, "/wrong"), ("no-branch", 403, "/no-branch")])
        auth_calls = []
        def auth(base, operation, body, timeout, expected=401, token=None):
            auth_calls.append((operation, expected, token))
            return smoke.check(status=expected, expected_status=expected)
        with patch.object(smoke.socket, "getaddrinfo", return_value=[(None, None, None, None, ("203.0.113.1", 443))]), \
             patch.object(smoke, "token_from_helper", side_effect=["secret-wrong", "secret-no-branch", "secret-positive"]), \
             patch.object(smoke, "authorization_check", side_effect=auth), \
             patch.object(smoke, "health_check", return_value=smoke.check(status=200)), \
             patch.object(smoke, "count_tokens_check", return_value=smoke.check(status=200)), \
             patch.object(smoke, "stream_check", return_value=smoke.check(status=200)):
            result = smoke.run(args)
        self.assertTrue(result["ok"])
        self.assertEqual(len(auth_calls), 6)
        self.assertEqual([status for _, status, token in auth_calls if token], [401, 401, 403, 403])
        self.assertNotIn("secret", json.dumps(result))
        response = Mock(status=200)
        with patch.object(smoke, "request", return_value=(Mock(), response, smoke.check(status=200))):
            result = smoke.authorization_check("https://gateway/claude", "v1/messages", "{}", 1, 403, "secret")
        self.assertEqual(result["error"], "unexpected_status")
        response.read.assert_not_called()

    def test_helper_output_validation_and_timeout_are_redacted(self):
        for output in (b"", b"null\n", b" \n", b"secret\nsecond\n", b"secret\n\n", b"secret token", b"secret\x00", b"\xff"):
            with patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output)):
                self.assertIsNone(smoke.token_from_helper("/helper", 120))
        for error in (subprocess.TimeoutExpired("secret", 1, output=b"secret"), OSError("secret")):
            with patch.object(smoke.subprocess, "run", side_effect=error):
                self.assertIsNone(smoke.token_from_helper("/helper", 120))
        with patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"token\r\n")) as run:
            self.assertEqual(smoke.token_from_helper("/helper", 120), "token")
        self.assertEqual(run.call_args.args, (["/helper"],))
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_truncated_http_content_length(self):
        body = b'event: message_start\ndata: {"type":"message_start"}\n\nevent: message_stop\ndata: {"type":"message_stop"}\n\n'
        wire = b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: 9999\r\n\r\n" + body
        response = smoke.http.client.HTTPResponse(Mock(makefile=Mock(return_value=io.BytesIO(wire))))
        response.begin()
        with patch.object(smoke, "request", return_value=(Mock(), response, smoke.check(status=200, ttfb=0))):
            self.assertEqual(smoke.stream_check("https://gateway/claude", "{}", {}, 1)["error"], "invalid_response")

    def test_first_event_is_observed_before_completion(self):
        start = b'event: message_start\ndata: {"type":"message_start"}\n\n'
        stop = b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
        for buffered in (False, True):
            release, seen, reading = threading.Event(), threading.Event(), threading.Event()
            response = Response(200, start + stop, "text/event-stream")
            lines = iter(response.body.splitlines(keepends=True))
            count = 0
            def readline():
                nonlocal count
                reading.set()
                if (buffered and count == 0) or (not buffered and count == 3):
                    if not release.wait(2):
                        raise TimeoutError
                count += 1
                return next(lines, b"")
            response.readline = readline
            original = smoke.SSERecords.feed
            def observe(records, line):
                event = original(records, line)
                if event == "message_start":
                    seen.set()
                return event
            with patch.object(smoke, "request", return_value=(Mock(), response, smoke.check(status=200, ttfb=0))), \
                 patch.object(smoke.SSERecords, "feed", observe), ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(smoke.stream_check, "https://gateway/claude", "{}", {}, 1)
                try:
                    self.assertTrue(reading.wait(1))
                    if buffered:
                        self.assertFalse(seen.wait(0.05))
                    else:
                        self.assertTrue(seen.wait(1))
                    self.assertFalse(future.done())
                finally:
                    release.set()
                result = future.result(timeout=2)
            self.assertIsNone(result["error"])
            self.assertIn("first_event_seconds", result)

    def test_stream_deadline_covers_headers_and_partial_lines_after_stop(self):
        start = b'event: message_start\ndata: {"type":"message_start"}\n\n'
        stop = b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
        mode = ["complete"]
        finished = {case: threading.Event() for case in ("headers", "partial", "heartbeat")}
        connections = []

        class Connection(http.client.HTTPConnection):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.closed = False
                connections.append(self)

            def close(self):
                self.closed = True
                super().close()

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args): pass

            def do_POST(self):
                case = mode[0]
                self.rfile.read(int(self.headers["Content-Length"]))
                try:
                    if case == "headers":
                        self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Drip: ")
                        self.wfile.flush()
                        for _ in range(100):
                            if finished[case].wait(0.02):
                                return
                            self.wfile.write(b"x")
                            self.wfile.flush()
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Content-Length", str(len(start + stop)) if case == "complete" else "9999")
                    self.end_headers()
                    self.wfile.write(start + stop)
                    self.wfile.flush()
                    if case in ("partial", "heartbeat"):
                        # One never-terminated line: a per-read socket timeout can be reset by each byte.
                        for _ in range(100):
                            if finished[case].wait(0.02):
                                return
                            self.wfile.write(b"x" if case == "partial" else b": heartbeat\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                url = f"https://127.0.0.1:{server.server_port}/claude"
                with patch.object(smoke.http.client, "HTTPSConnection", Connection):
                    for case in ("complete", "headers", "partial", "heartbeat"):
                        mode[0] = case
                        try:
                            before = time.monotonic()
                            result = smoke.stream_check(url, "{}", {}, 0.12)
                            elapsed = time.monotonic() - before
                            with self.subTest(case=case):
                                self.assertEqual(result["error"], None if case == "complete" else "timeout")
                                self.assertLess(elapsed, 0.6)
                                self.assertTrue(connections[-1].closed)
                                if case in ("partial", "heartbeat"):
                                    self.assertIn("first_event_seconds", result)
                        finally:
                            if case in finished:
                                finished[case].set()
            finally:
                for event in finished.values():
                    event.set()
                server.shutdown()
                thread.join()


if __name__ == "__main__":
    unittest.main()
