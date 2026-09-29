#!/usr/bin/env python3
"""Run a manual Claude Code gateway canary in an isolated temporary repository."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit


REQUIRED_ENVIRONMENT = (
    "ANTHROPIC_BASE_URL",
    "APIM_AUDIENCE",
    "APIM_TENANT_ID",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
)
TASK_SOURCE = 'def greeting():\n    return "after"\n'
TEST_SOURCE = """from pathlib import Path
from task import greeting

assert greeting() == \"after\"
marker = Path(\".canary-test-ran\")
marker.write_text(str(int(marker.read_text()) + 1 if marker.exists() else 1))
"""
SAFE_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def emit(ok: bool, mode: str, requests: int, error: str | None = None) -> int:
    result = {"ok": ok, "mode": mode, "requests": requests}
    if error:
        result["error"] = error
    print(json.dumps(result, sort_keys=True))
    return 0 if ok else 1


def inference_error(invocations: int, error: str) -> int:
    print(json.dumps({"ok": False, "mode": "inference-only", "client_invocations": invocations,
                      "error": error}, sort_keys=True))
    return 1


def client_command(binary: str, prompt: str, budget: str) -> list[str]:
    return [
        binary,
        "--print",
        "--output-format", "json",
        "--no-session-persistence",
        "--max-budget-usd", budget,
        "--permission-mode", "acceptEdits",
        "--tools", "Read,Edit,Bash",
        "--allowed-tools", "Read,Edit,Bash(python3 test_task.py)",
        "--disallowed-tools", "WebFetch,WebSearch",
        prompt,
    ]


def run_request(binary: str, directory: Path, prompt: str, budget: str, timeout: float) -> bool:
    try:
        completed = subprocess.run(
            client_command(binary, prompt, budget),
            cwd=directory,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def valid_task(directory: Path, expected_runs: int) -> bool:
    try:
        task_source = (directory / "task.py").read_text()
        test_source = (directory / "test_task.py").read_text()
        marker = (directory / ".canary-test-ran").read_text()
    except OSError:
        return False
    if task_source != TASK_SOURCE or test_source != TEST_SOURCE or marker != str(expected_runs):
        return False
    return subprocess.run(
        [sys.executable, "-c", "from task import greeting; assert greeting() == 'after'"],
        cwd=directory,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def inference_only(args: argparse.Namespace) -> int:
    model = args.model
    gateway = os.environ.get("ANTHROPIC_BASE_URL", "")
    try:
        url = urlsplit(gateway)
        hostname = url.hostname
    except ValueError:
        return inference_error(0, "invalid_inference_configuration")
    helper = Path(args.token_helper) if args.token_helper else None
    if (not model or not SAFE_MODEL.fullmatch(model) or not helper or not helper.is_absolute()
            or not helper.is_file() or not os.access(helper, os.X_OK)
            or url.scheme != "https" or not hostname or url.username or url.password
            or url.query or url.fragment or url.path.rstrip("/") != "/claude"
            or not os.environ.get("APIM_AUDIENCE") or not os.environ.get("APIM_TENANT_ID")):
        return inference_error(0, "invalid_inference_configuration")
    executable = shutil.which(args.claude_bin)
    if not executable:
        return inference_error(0, "claude_not_found")

    with tempfile.TemporaryDirectory(prefix="claude-code-inference-") as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "config").mkdir()
        environment = {key: os.environ[key] for key in (
            "PATH", "HOME", "AZURE_CONFIG_DIR", "SSL_CERT_FILE", "SSL_CERT_DIR",
            "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
        ) if key in os.environ}
        environment.update({
            "ANTHROPIC_BASE_URL": gateway,
            "APIM_AUDIENCE": os.environ["APIM_AUDIENCE"],
            "APIM_TENANT_ID": os.environ["APIM_TENANT_ID"],
            "CLAUDE_CONFIG_DIR": str(directory / "config"),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        })
        command = [
            str(Path(executable).resolve()), "--bare", "--print", "--tools", "", "--strict-mcp-config",
            "--mcp-config", '{"mcpServers":{}}', "--setting-sources", "",
            "--disable-slash-commands", "--no-session-persistence",
            "--settings", json.dumps({"apiKeyHelper": shlex.quote(str(helper))}),
            "--model", model, "--system-prompt", "Reply only with CANARY_OK.",
            "--max-budget-usd", args.max_budget_usd, "--output-format", "json", "CANARY_OK",
        ]
        try:
            process = subprocess.Popen(command, cwd=directory, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       start_new_session=True)
            try:
                stdout, _ = process.communicate(timeout=args.timeout_seconds)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
                return inference_error(1, "claude_request_failed")
        except OSError:
            return inference_error(1, "claude_request_failed")
        if process.returncode != 0:
            return inference_error(1, "claude_request_failed")
        try:
            response = json.loads(stdout)
            reported = response["modelUsage"]
            if not isinstance(reported, dict) or not reported:
                raise ValueError
            if response["is_error"] is not False or response["result"] != "CANARY_OK":
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return inference_error(1, "invalid_client_result")
        if set(reported) != {model}:
            print(json.dumps({"ok": False, "mode": "inference-only", "client_invocations": 1,
                              "requested_model": model, "reported_model_count": len(reported),
                              "error": "model_mismatch"}, sort_keys=True))
            return 1
        print(json.dumps({"ok": True, "mode": "inference-only", "client_invocations": 1,
                          "requested_model": model, "reported_models": [model]}, sort_keys=True))
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-bin", default="claude", help="installed Claude Code binary")
    parser.add_argument("--max-budget-usd", default="0.10", help="positive per-request Claude Code budget")
    parser.add_argument("--timeout-seconds", type=float, default=120, help="positive per-request timeout")
    parser.add_argument("--inference-only", action="store_true", help="isolated, no-tools explicit-model inference")
    parser.add_argument("--model", help="exact deployed model name for inference-only mode")
    parser.add_argument("--token-helper", help="absolute executable token helper path for inference-only mode")
    parser.add_argument(
        "--refresh-after-seconds",
        type=float,
        help="wait, then launch a separate Claude process; not a same-session refresh test",
    )
    args = parser.parse_args(argv)
    mode = "inference-only" if args.inference_only else ("separate-process-wait" if args.refresh_after_seconds is not None else "basic")

    try:
        if (not math.isfinite(float(args.max_budget_usd)) or float(args.max_budget_usd) <= 0
                or not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0
                or args.inference_only and args.timeout_seconds > 300):
            raise ValueError
        if (args.refresh_after_seconds is not None
                and (not math.isfinite(args.refresh_after_seconds) or args.refresh_after_seconds < 0)):
            raise ValueError
    except ValueError:
        return inference_error(0, "invalid_argument") if args.inference_only else emit(False, mode, 0, "invalid_argument")
    if (args.inference_only and args.refresh_after_seconds is not None
            or not args.inference_only and (args.model is not None or args.token_helper is not None)):
        return inference_error(0, "invalid_argument") if args.inference_only else emit(False, mode, 0, "invalid_argument")
    if args.inference_only:
        return inference_only(args)
    if any(not os.environ.get(name) for name in REQUIRED_ENVIRONMENT):
        return emit(False, mode, 0, "gateway_environment_missing")
    if not shutil.which(args.claude_bin):
        return emit(False, mode, 0, "claude_not_found")

    with tempfile.TemporaryDirectory(prefix="claude-code-canary-") as temporary_directory:
        directory = Path(temporary_directory)
        try:
            subprocess.run(["git", "init", "--quiet"], cwd=directory, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (directory / "task.py").write_text('def greeting():\n    return "before"\n')
            (directory / "test_task.py").write_text(TEST_SOURCE)
        except (OSError, subprocess.CalledProcessError):
            return emit(False, mode, 0, "temporary_repository_failed")

        first_prompt = (
            "Read task.py. Change only greeting() so it returns 'after'. Then run "
            "python3 test_task.py. Do not modify test_task.py or create files yourself; "
            "the test creates its marker."
        )
        if not run_request(args.claude_bin, directory, first_prompt, args.max_budget_usd, args.timeout_seconds):
            return emit(False, mode, 1, "claude_request_failed")
        if not valid_task(directory, 1):
            return emit(False, mode, 1, "task_verification_failed")

        if args.refresh_after_seconds is None:
            return emit(True, mode, 1)

        try:
            time.sleep(args.refresh_after_seconds)
        except (OverflowError, OSError, ValueError):
            return emit(False, mode, 1, "invalid_argument")
        second_prompt = "Read task.py and run python3 test_task.py. Do not edit any files."
        if not run_request(args.claude_bin, directory, second_prompt, args.max_budget_usd, args.timeout_seconds):
            return emit(False, mode, 2, "claude_request_failed")
        if not valid_task(directory, 2):
            return emit(False, mode, 2, "task_verification_failed")
    return emit(True, mode, 2)


if __name__ == "__main__":
    raise SystemExit(main())
