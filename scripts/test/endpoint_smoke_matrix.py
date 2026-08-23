#!/usr/bin/env python3
"""Exercise the gateway-local and authenticated Claude endpoint checks once."""

import argparse
from collections import OrderedDict
import http.client
import json
import math
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


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
    name, separator, base_url = value.partition("=")
    parsed = urlsplit(base_url)
    if (not separator or not name or parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path.rstrip("/") != "/claude"):
        raise ValueError("endpoint must be name=https://host/claude")
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


def request(url, method, body, headers, timeout):
    parsed = urlsplit(url)
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=timeout)
    started = time.monotonic()
    try:
        connected = time.monotonic()
        connection.connect()
        connect_seconds = duration(connected)
        peer_address = connection.sock.getpeername()[0] if connection.sock else None
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


def unauthenticated_check(base_url, body, timeout):
    connection, response, result = request(
        route(base_url, "v1/messages"), "POST", body,
        {"content-type": "application/json", "anthropic-version": "2023-06-01"}, timeout,
    )
    if response:
        try:
            if result["status"] != 401:
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
    connection, response, result = request(route(base_url, "v1/messages"), "POST", body, headers, timeout)
    if response:
        def valid(item):
            if not (item.getheader("Content-Type") or "").lower().startswith("text/event-stream"):
                return False
            events = set()
            while line := item.readline():
                if line.startswith(b"event:"):
                    events.add(line[6:].strip().decode())
                    if {"message_start", "message_stop"} <= events:
                        return True
            return False
        finish(connection, response, result, valid)
    return result


def token_from_helper(helper, timeout):
    try:
        completed = subprocess.run(
            [helper], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False,
        )
        token = completed.stdout.decode().strip()
        if completed.returncode or not token or "\r" in token or "\n" in token:
            return None
        return token
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None


def unavailable_check(error):
    return check(error=error)


def run(args):
    models = OrderedDict(args.models)
    model = models["sonnet"]
    stream_body = json.dumps({"model": model, "max_tokens": 8, "stream": True,
                              "messages": [{"role": "user", "content": "Reply only OK"}]})
    results = []
    for name, base_url in args.endpoints:
        host = urlsplit(base_url).hostname
        try:
            addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
            dns_error = None
        except socket.gaierror:
            addresses, dns_error = [], "dns_error"
        checks = {"health": health_check(base_url, args.timeout) if not dns_error else unavailable_check(dns_error),
                  "unauthenticated_messages": (unauthenticated_check(base_url, stream_body, args.timeout)
                                                if not dns_error else unavailable_check(dns_error))}
        results.append({"base_url": base_url, "checks": checks, "dns_addresses": addresses, "name": name})

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
        "ok": all(item["ok"] for item in results),
        "phase": args.phase,
        "schema_version": 1,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", action="append", required=True, help="name=https://host/claude")
    parser.add_argument("--token-helper", required=True)
    parser.add_argument("--model", action="append", required=True,
                        help="role=pinned-deployment; repeat for opus, sonnet, and haiku")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--phase", choices=("readiness", "observe-failover", "observe-failback", "rollback-before", "rollback-after"), default="readiness")
    args = parser.parse_args(argv)
    try:
        args.endpoints = [endpoint(value) for value in args.endpoint]
        args.models = [model_mapping(value) for value in args.model]
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
