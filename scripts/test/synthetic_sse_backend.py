#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import time

HOST = os.getenv("SSE_HOST", "127.0.0.1")
PORT = int(os.getenv("SSE_PORT", "8088"))
EVENT_COUNT = int(os.getenv("SSE_EVENT_COUNT", "30"))
EVENT_INTERVAL_MS = int(os.getenv("SSE_EVENT_INTERVAL_MS", "200"))


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/messages":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("content-length", "0"))
        _ = self.rfile.read(length)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        self.wfile.write(b"event: message_start\ndata: {\"type\":\"message_start\"}\n\n")
        self.wfile.flush()
        for i in range(EVENT_COUNT):
            payload = {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": f"token-{i}"}}
            line = f"event: content_block_delta\ndata: {json.dumps(payload)}\n\n".encode("utf-8")
            self.wfile.write(line)
            self.wfile.flush()
            time.sleep(EVENT_INTERVAL_MS / 1000.0)

        self.wfile.write(b"event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n")
        self.wfile.flush()
        self.close_connection = True

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Synthetic SSE backend listening on http://{HOST}:{PORT}/v1/messages")
    server.serve_forever()
