#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
CANARY = REPO_ROOT / "scripts/test/claude_code_canary.py"


class ClaudeCodeCanaryTests(unittest.TestCase):
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

    def test_refresh_mode_makes_a_second_request_without_waiting_by_default(self) -> None:
        result, calls, _ = self.run_canary(["--refresh-after-seconds", "0"])
        self.assertEqual(result, {"mode": "refresh", "ok": True, "requests": 2})
        self.assertEqual(calls.read_text(), "xx")


if __name__ == "__main__":
    unittest.main()
