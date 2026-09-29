"""Incremental validation of complete Anthropic SSE records, not text matches."""

import json


def is_event_stream(content_type):
    return content_type.split(";", 1)[0].strip().lower() == "text/event-stream"


class SSERecords:
    def __init__(self):
        self.event = None
        self.data = []
        self.started = False
        self.completed = False

    def feed(self, line):
        if not line.endswith(b"\n"):
            raise ValueError("truncated_sse")
        text = line.decode("utf-8").removesuffix("\n").removesuffix("\r")
        if text:
            field, _, value = text.partition(":")
            value = value.removeprefix(" ")
            if field == "event":
                self.event = value
            elif field == "data":
                self.data.append(value)
            return None
        event, data = self.event, self.data
        self.event, self.data = None, []
        if event is None and not data:
            return None  # SSE comments/keepalives are not events.
        payload = json.loads("\n".join(data))
        if not isinstance(payload, dict) or payload.get("type") != event:
            raise ValueError("invalid_sse_record")
        if not self.completed:
            if event == "error":
                raise ValueError("sse_error")
            if event == "message_start":
                self.started = True
            if event == "message_stop":
                if not self.started:
                    raise ValueError("sse_stop_before_start")
                self.completed = True
        return event

    def finish(self):
        if not self.completed or self.event is not None or self.data:
            raise ValueError("incomplete_sse")
