#!/usr/bin/env python3
"""Exercise the gateway-local and authenticated Claude endpoint checks once."""

import argparse
from collections import OrderedDict
import http.client
import json
import math
from pathlib import Path
import re
import socket
import ssl
import subprocess
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from sse_records import SSERecords, is_event_stream


def check(status=None, connect=None, ttfb=None, duration=None, error=None, **extra):
    return {
        "connect_seconds": connect,
        "duration_seconds": duration,
        "error": error,
        "status": status,
        "ttfb_seconds": ttfb,
        **extra,
    }


def error_category(error):
    if isinstance(error, socket.gaierror):
        return "dns_error"
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(error, ssl.SSLError):
        return "tls_error"
    if isinstance(error, http.client.HTTPException):
        return "protocol_error"
    if isinstance(error, OSError):
        return "network_error"
    return "internal_error"


def endpoint(value):
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("endpoint must contain no control characters")
    name, separator, base_url = value.partition("=")
    parsed = urlsplit(base_url)
    if (not separator or not name or parsed.scheme != "https" or not parsed.hostname
            or "@" in parsed.netloc or "?" in base_url or "#" in base_url
            or parsed.path.rstrip("/") != "/claude"):
        raise ValueError("endpoint must be name=https://host/claude")
    if parsed.port == 0 or parsed.netloc.endswith(":"):
        raise ValueError("endpoint port must be valid")
    return name, urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def model_mapping(value):
    role, separator, deployment = value.partition("=")
    if not separator or not role or not deployment:
        raise ValueError("model must be role=pinned-deployment")
    return role, deployment


def route(base_url, suffix):
    parsed = urlsplit(base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, f"{parsed.path}/{suffix}", "", ""))


def duration(start):
    return round(time.monotonic() - start, 6)


def request(url, method, body, headers, timeout, on_connect=None):
    parsed = urlsplit(url)
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=timeout)
    started = time.monotonic()
    try:
        connected = time.monotonic()
        connection.connect()
        connect_seconds = duration(connected)
        peer_address = connection.sock.getpeername()[0] if connection.sock else None
        if on_connect:
            on_connect(connection.sock)
        connection.request(method, parsed.path or "/", body=body, headers=headers)
        response = connection.getresponse()
        return connection, response, check(
            status=response.status,
            connect=connect_seconds,
            ttfb=duration(started),
            duration=None,
            peer_address=peer_address,
        )
    except Exception as caught:  # Report only a category; exceptions can contain endpoint details.
        connection.close()
        return None, None, check(duration=duration(started), error=error_category(caught))


def finish(connection, response, result, validator):
    started = time.monotonic()
    try:
        if result["status"] != 200:
            result["error"] = "unexpected_status"
        elif not validator(response):
            result["error"] = "invalid_response"
    except Exception:
        result["error"] = "invalid_response"
    finally:
        response.close()
        connection.close()
        result["duration_seconds"] = round(result["ttfb_seconds"] + duration(started), 6)
    return result


def health_check(base_url, timeout):
    connection, response, result = request(route(base_url, "health"), "GET", None, {}, timeout)
    result["label"] = "gateway-local"
    if response:
        finish(connection, response, result, lambda item: item.read().decode().strip().lower() == "healthy")
    return result


def authorization_check(base_url, operation, body, timeout, expected=401, token=None):
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    connection, response, result = request(
        route(base_url, operation), "POST", body, headers, timeout,
    )
    result["expected_status"] = expected
    if response:
        try:
            if result["status"] != expected:
                result["error"] = "unexpected_status"
        finally:
            response.close()
            connection.close()
            result["duration_seconds"] = result["ttfb_seconds"]
    return result


def count_tokens_check(base_url, body, headers, timeout):
    connection, response, result = request(route(base_url, "v1/messages/count_tokens"), "POST", body, headers, timeout)
    if response:
        def valid(item):
            return isinstance(json.loads(item.read().decode()).get("input_tokens"), int)
        finish(connection, response, result, valid)
    return result


def stream_check(base_url, body, headers, timeout):
    started = time.monotonic()
    deadline = started + timeout
    expired = threading.Event()
    timer = None

    def on_connect(sock):
        nonlocal timer
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        if sock is not None:
            def interrupt():
                expired.set()
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            timer = threading.Timer(remaining, interrupt)
            timer.start()

    try:
        connection, response, result = request(route(base_url, "v1/messages"), "POST", body, headers, timeout, on_connect)
        if response:
            def valid(item):
                if not is_event_stream(item.getheader("Content-Type") or ""):
                    return False
                records = SSERecords()
                while line := item.readline():
                    if records.feed(line) and "first_event_seconds" not in result:
                        result["first_event_seconds"] = duration(started)
                if getattr(item, "length", None) not in (None, 0):
                    return False
                records.finish()
                return True
            finish(connection, response, result, valid)
        if expired.is_set() or time.monotonic() >= deadline:
            result["error"] = "timeout"
    finally:
        if timer:
            timer.cancel()
            timer.join()
    return result


def token_from_helper(helper, timeout):
    try:
        completed = subprocess.run(
            [helper], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=min(timeout, 30), check=False,
        )
        token = completed.stdout.decode().removesuffix("\n").removesuffix("\r")
        if (completed.returncode or not token or token == "null"
                or any(char.isspace() or not 33 <= ord(char) <= 126 for char in token)):
            return None
        return token
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None


def unavailable_check(error):
    return check(error=error)


def run(args):
    negative_cases = getattr(args, "negative_cases", [])
    if negative_cases and not getattr(args, "allow_negative_auth", False):
        raise ValueError("negative auth cases require --allow-negative-auth")
    models = OrderedDict(args.models)
    model = models["sonnet"]
    stream_body = json.dumps({"model": model, "max_tokens": 8, "stream": True,
                              "messages": [{"role": "user", "content": "Reply only OK"}]})
    count_body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Reply only OK"}]})
    operations = {"messages": ("v1/messages", stream_body),
                  "count_tokens": ("v1/messages/count_tokens", count_body)}
    results = []
    for name, base_url in args.endpoints:
        host = urlsplit(base_url).hostname
        try:
            addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
            dns_error = None
        except socket.gaierror:
            addresses, dns_error = [], "dns_error"
        checks = {"health": health_check(base_url, args.timeout) if not dns_error else unavailable_check(dns_error)}
        for label, (operation, body) in operations.items():
            checks[f"unauthenticated_{label}"] = (
                authorization_check(base_url, operation, body, args.timeout)
                if not dns_error else check(error=dns_error, expected_status=401))
        results.append({"base_url": base_url, "checks": checks, "dns_addresses": addresses, "name": name})

    for label, expected, helper in negative_cases:
        negative_token = token_from_helper(helper, args.timeout)
        for item in results:
            for operation_label, (operation, body) in operations.items():
                error = "dns_error" if not item["dns_addresses"] else "helper_error" if not negative_token else None
                item["checks"][f"negative_{label}_{operation_label}"] = (
                    check(error=error, expected_status=expected) if error else
                    authorization_check(item["base_url"], operation, body, args.timeout, expected, negative_token))
        negative_token = None

    token = token_from_helper(args.token_helper, args.timeout)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json",
               "anthropic-version": "2023-06-01"} if token else None
    for item in results:
        checks = item["checks"]
        if not item["dns_addresses"]:
            checks["count_tokens"] = {role: unavailable_check("dns_error") for role in models}
            checks["messages_sse"] = unavailable_check("dns_error")
        elif not headers:
            checks["count_tokens"] = {role: unavailable_check("helper_error") for role in models}
            checks["messages_sse"] = unavailable_check("helper_error")
        else:
            checks["count_tokens"] = {
                role: count_tokens_check(
                    item["base_url"],
                    json.dumps({"model": deployment, "messages": [{"role": "user", "content": "Reply only OK"}]}),
                    headers,
                    args.timeout,
                )
                for role, deployment in models.items()
            }
            checks["messages_sse"] = stream_check(item["base_url"], stream_body, headers, args.timeout)
        flat_checks = [value for value in checks.values() if isinstance(value, dict) and "error" in value]
        flat_checks.extend(checks["count_tokens"].values())
        item["ok"] = all(value["error"] is None for value in flat_checks)
    return {
        "endpoints": results,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "health_semantics": "gateway-local-only",
        "models": models,
        "negative_auth_cases": [label for label, _, _ in negative_cases],
        "negative_auth_coverage": "provided-cases-only; unprovided cases not tested",
        "ok": all(item["ok"] for item in results),
        "phase": args.phase,
        "schema_version": 1,
    }


def negative_case(value):
    parts = value.split("=", 2)
    if (len(parts) != 3 or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", parts[0])
            or parts[1] not in {"401", "403"} or not Path(parts[2]).is_absolute()
            or any(ord(char) < 32 or ord(char) == 127 for char in parts[2])):
        raise ValueError("negative case must be safe-label=401|403=/absolute/helper")
    return parts[0], int(parts[1]), parts[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", action="append", required=True, help="name=https://host/claude")
    parser.add_argument("--token-helper", required=True)
    parser.add_argument("--negative-case", action="append", default=[], help="label=401|403=/absolute/helper; repeatable")
    parser.add_argument("--allow-negative-auth", action="store_true", help="approve negative identity requests")
    parser.add_argument("--model", action="append", required=True,
                        help="role=pinned-deployment; repeat for opus, sonnet, and haiku")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--phase", choices=("readiness", "observe-failover", "observe-failback", "rollback-before", "rollback-after"), default="readiness")
    args = parser.parse_args(argv)
    try:
        args.endpoints = [endpoint(value) for value in args.endpoint]
        args.models = [model_mapping(value) for value in args.model]
        args.negative_cases = [negative_case(value) for value in args.negative_case]
        if ((args.negative_cases and not args.allow_negative_auth)
                or len({label for label, _, _ in args.negative_cases}) != len(args.negative_cases)):
            raise ValueError("negative cases require opt-in and unique labels")
        if (len({name for name, _ in args.endpoints}) != len(args.endpoints)
                or len({role for role, _ in args.models}) != len(args.models)
                or {role for role, _ in args.models} != {"opus", "sonnet", "haiku"}
                or not math.isfinite(args.timeout) or args.timeout <= 0):
            raise ValueError("names, model roles, and timeout must be unique and valid")
    except ValueError as caught:
        parser.error(str(caught))
    result = run(args)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
