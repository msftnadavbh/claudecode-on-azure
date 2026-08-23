#!/usr/bin/env python3
import argparse
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


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
            return Response(200, b'{"input_tokens":1}')
        if self.path.endswith("messages"):
            return Response(401) if not self.authorized else Response(
                200, b"event: message_start\n\nevent: message_stop\n\n", "text/event-stream"
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

    def test_endpoint_failure(self):
        result = self.run_smoke(health_status=503)
        self.assertFalse(result["ok"])
        self.assertEqual(result["endpoints"][0]["checks"]["health"]["error"], "unexpected_status")


if __name__ == "__main__":
    unittest.main()
