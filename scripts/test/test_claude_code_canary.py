#!/usr/bin/env python3
import json
import io
from contextlib import redirect_stdout
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import claude_code_canary


REPO_ROOT = Path(__file__).resolve().parents[2]
CANARY = REPO_ROOT / "scripts/test/claude_code_canary.py"


class ClaudeCodeCanaryTests(unittest.TestCase):
    def test_missing_tenant_stops_before_client_launch(self):
        environment = {name: "configured" for name in claude_code_canary.REQUIRED_ENVIRONMENT if name != "APIM_TENANT_ID"}
        output = io.StringIO()
        with patch.dict(os.environ, environment, clear=True), patch.object(claude_code_canary, "run_request") as request, redirect_stdout(output):
            self.assertEqual(claude_code_canary.main([]), 1)
        request.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["error"], "gateway_environment_missing")

    def run_canary(self, extra_args: list[str] = []) -> tuple[dict, Path]:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        calls = root / "calls"
        arguments = root / "arguments"
        claude = root / "claude"
        claude.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            f"printf x >> {str(calls)!r}\n"
            f"printf '%s\\n' \"$@\" > {str(arguments)!r}\n"
            "if [[ $* == *'Change only greeting'* ]]; then\n"
            "  printf 'def greeting():\\n    return \"after\"\\n' > task.py\n"
            "fi\n"
            "python3 test_task.py\n"
            "printf '{}\\n'\n"
        )
        claude.chmod(0o700)
        env = {
            **os.environ,
            "ANTHROPIC_BASE_URL": "https://gateway.example/claude",
            "APIM_AUDIENCE": "api://gateway",
            "APIM_TENANT_ID": "11111111-1111-1111-1111-111111111111",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku",
        }
        completed = subprocess.run(
            [sys.executable, CANARY, "--claude-bin", str(claude), *extra_args],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return json.loads(completed.stdout), calls, arguments

    def test_basic_canary_runs_disposable_edit_and_test(self) -> None:
        result, calls, arguments = self.run_canary()
        self.assertEqual(result, {"mode": "basic", "ok": True, "requests": 1})
        self.assertEqual(calls.read_text(), "x")
        self.assertEqual(arguments.read_text().splitlines()[:14], [
            "--print", "--output-format", "json", "--no-session-persistence",
            "--max-budget-usd", "0.10", "--permission-mode", "acceptEdits",
            "--tools", "Read,Edit,Bash", "--allowed-tools", "Read,Edit,Bash(python3 test_task.py)",
            "--disallowed-tools", "WebFetch,WebSearch",
        ])

    def test_wait_mode_launches_a_second_process(self) -> None:
        result, calls, _ = self.run_canary(["--refresh-after-seconds", "0"])
        self.assertEqual(result, {"mode": "separate-process-wait", "ok": True, "requests": 2})
        self.assertEqual(calls.read_text(), "xx")

    def test_inference_requires_model_and_helper_before_launch(self):
        environment = {"ANTHROPIC_BASE_URL": "https://gateway.example/claude",
                       "APIM_AUDIENCE": "api://gateway", "APIM_TENANT_ID": "tenant"}
        for args in (["--inference-only"], ["--inference-only", "--model", "claude-opus-5-5"]):
            output = io.StringIO()
            with patch.dict(os.environ, environment, clear=True), patch.object(claude_code_canary.subprocess, "Popen") as request, redirect_stdout(output):
                self.assertEqual(claude_code_canary.main(args), 1)
            request.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["client_invocations"], 0)

    def test_inference_only_isolated_and_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = root / "helper with space"
            helper.write_text("#!/bin/sh\nexit 0\n")
            helper.chmod(0o700)
            claude = root / "claude"
            capture = root / "capture.json"
            claude.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                              "from pathlib import Path\n"
                              f"Path({str(capture)!r}).write_text(json.dumps({{'args': sys.argv[1:], 'env': dict(os.environ), 'binary': sys.argv[0], 'cwd': os.getcwd()}}))\n"
                              "print(json.dumps({'is_error': False, 'result': 'CANARY_OK', "
                              "'modelUsage': {'claude-opus-5-5': {}}}))\n")
            claude.chmod(0o700)
            link = root / "claude-link"
            link.symlink_to(claude)
            env = {**os.environ, "ANTHROPIC_BASE_URL": "https://gateway.example/claude",
                   "APIM_AUDIENCE": "api://gateway", "APIM_TENANT_ID": "tenant",
                   "ANTHROPIC_API_KEY": "forbidden", "CLAUDE_CODE_USE_FOUNDRY": "1",
                   "ANTHROPIC_DEFAULT_OPUS_MODEL": "wrong", "CLAUDE_CONFIG_DIR": "/wrong",
                   "CLAUDE_CODE_OAUTH_TOKEN": "forbidden", "ANTHROPIC_FOUNDRY_BASE_URL": "forbidden",
                   "ANTHROPIC_AUTH_TOKEN": "forbidden", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "0",
                   "PATH": str(root) + os.pathsep + os.environ.get("PATH", "")}
            command = [sys.executable, CANARY, "--inference-only", "--model", "claude-opus-5-5",
                       "--token-helper", str(helper), "--claude-bin", "claude-link"]
            def run(*extra, environment=env):
                return subprocess.run([*command, *extra], env=environment, capture_output=True, text=True)

            completed = run()
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {"ok": True, "mode": "inference-only",
                             "client_invocations": 1, "requested_model": "claude-opus-5-5",
                             "reported_models": ["claude-opus-5-5"]})
            captured = json.loads(capture.read_text())
            arguments, child_env = captured["args"], captured["env"]
            self.assertEqual(captured["binary"], str(claude.resolve()))
            self.assertNotEqual(captured["cwd"], os.getcwd())
            self.assertFalse(Path(captured["cwd"]).exists())
            for flag, value in (("--model", "claude-opus-5-5"), ("--tools", ""),
                                ("--mcp-config", '{"mcpServers":{}}'), ("--setting-sources", ""),
                                ("--output-format", "json")):
                self.assertEqual(arguments[arguments.index(flag) + 1], value)
            for flag in ("--bare", "--print", "--strict-mcp-config", "--disable-slash-commands",
                         "--no-session-persistence", "--system-prompt", "--max-budget-usd"):
                self.assertIn(flag, arguments)
            self.assertEqual(json.loads(arguments[arguments.index("--settings") + 1]),
                             {"apiKeyHelper": "'" + str(helper) + "'"})
            self.assertEqual(child_env["ANTHROPIC_BASE_URL"], env["ANTHROPIC_BASE_URL"])
            self.assertEqual(child_env["APIM_AUDIENCE"], env["APIM_AUDIENCE"])
            self.assertEqual(child_env["APIM_TENANT_ID"], env["APIM_TENANT_ID"])
            self.assertEqual(child_env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"], "1")
            self.assertNotEqual(child_env["CLAUDE_CONFIG_DIR"], "/wrong")
            for name in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_OAUTH_TOKEN",
                         "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_FOUNDRY_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
                self.assertNotIn(name, child_env)
            self.assertFalse(Path(child_env["CLAUDE_CONFIG_DIR"]).exists())

            sentinel = "SECRET_DO_NOT_PRINT"
            claude.write_text(claude.read_text().replace("'claude-opus-5-5': {}", f"'{sentinel}': {{}}"))
            mismatch = run()
            self.assertEqual(mismatch.returncode, 1)
            self.assertEqual(json.loads(mismatch.stdout)["reported_model_count"], 1)
            self.assertEqual(json.loads(mismatch.stdout)["error"], "model_mismatch")
            self.assertNotIn(sentinel, mismatch.stdout + mismatch.stderr)
            claude.write_text(claude.read_text().replace("'result': 'CANARY_OK'", "'result': 'wrong'"))
            bad = run()
            self.assertEqual(bad.returncode, 1)
            self.assertEqual(json.loads(bad.stdout)["error"], "invalid_client_result")
            for body, expected in ((f"print({sentinel!r}); print({sentinel!r}, file=sys.stderr)\n", "invalid_client_result"),
                                   (f"print({sentinel!r}); print({sentinel!r}, file=sys.stderr); sys.exit(2)\n", "claude_request_failed"),
                                   ("print(json.dumps({'is_error': True, 'result': 'CANARY_OK', 'modelUsage': {'claude-opus-5-5': {}}}))\n", "invalid_client_result")):
                claude.write_text("#!/usr/bin/env python3\nimport json, sys\n" + body)
                failed = run()
                self.assertEqual(failed.returncode, 1)
                self.assertEqual(json.loads(failed.stdout)["error"], expected)
                self.assertNotIn(sentinel, failed.stdout + failed.stderr)
            capture.unlink()
            for extra, environment in ((["--refresh-after-seconds", "0"], env),
                                       (["--timeout-seconds", "301"], env),
                                       (["--timeout-seconds", "1e309"], env),
                                       ([], {**env, "ANTHROPIC_BASE_URL": "http://gateway.example/claude"}),
                                       ([], {**env, "APIM_AUDIENCE": ""})):
                rejected = run(*extra, environment=environment)
                self.assertEqual(rejected.returncode, 1)
                self.assertEqual(json.loads(rejected.stdout)["client_invocations"], 0)
                self.assertFalse(capture.exists())

    def test_inference_timeout_kills_helper_descendants(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = root / "helper"
            helper.write_text("#!/bin/sh\nexit 0\n")
            helper.chmod(0o700)
            marker = root / "survived"
            claude = root / "claude"
            claude.write_text("#!/usr/bin/env python3\nimport subprocess, sys, time\n"
                              "subprocess.Popen([sys.executable, '-c', "
                              f"'import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()'])\n"
                              "time.sleep(5)\n")
            claude.chmod(0o700)
            env = {**os.environ, "ANTHROPIC_BASE_URL": "https://gateway.example/claude",
                   "APIM_AUDIENCE": "api://gateway", "APIM_TENANT_ID": "tenant"}
            completed = subprocess.run([sys.executable, CANARY, "--inference-only", "--model", "claude-opus-5-5",
                                        "--token-helper", str(helper), "--claude-bin", str(claude),
                                        "--timeout-seconds", "0.3"], env=env, capture_output=True, text=True, timeout=4)
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(json.loads(completed.stdout)["error"], "claude_request_failed")
            import time
            time.sleep(1.1)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
