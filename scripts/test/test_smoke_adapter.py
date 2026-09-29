"""Exercise only the shell adapter with a fake Python command, never a token helper."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SmokeAdapterTests(unittest.TestCase):
    def test_arguments_prerequisites_and_exit_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            captured = directory / "arguments"
            helper_marker = directory / "helper-ran"
            helper = directory / "helper with spaces"
            helper.write_text('#!/bin/bash\nprintf called > "$HELPER_MARKER"\nexit 99\n')
            helper.chmod(0o700)
            python = directory / "python3"
            python.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$CAPTURED"\nexit "$FAKE_EXIT"\n')
            python.chmod(0o700)
            env = {**os.environ, "PATH": f"{directory}:{os.environ['PATH']}",
                   "CAPTURED": str(captured), "HELPER_MARKER": str(helper_marker), "FAKE_EXIT": "0",
                   "APIM_BASE_URL": "https://gateway.example/claude", "APIM_TOKEN_HELPER": str(helper),
                   "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus", "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet",
                   "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku"}
            for code in (0, 1, 23):
                with self.subTest(code=code):
                    result = subprocess.run([ROOT / "scripts/test/smoke.sh"], cwd=directory,
                                            env={**env, "FAKE_EXIT": str(code)}, capture_output=True)
                    self.assertEqual(result.returncode, code)
                    self.assertEqual(captured.read_bytes().split(b"\0")[:-1], [value.encode() for value in (
                        str(ROOT / "scripts/test/endpoint_smoke_matrix.py"), "--endpoint", "primary=https://gateway.example/claude",
                        "--token-helper", str(helper), "--model", "opus=opus", "--model", "sonnet=sonnet", "--model", "haiku=haiku")])
                    self.assertFalse(helper_marker.exists())
            captured.unlink()
            for missing in ("APIM_BASE_URL", "APIM_TOKEN_HELPER", "ANTHROPIC_DEFAULT_OPUS_MODEL",
                            "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
                with self.subTest(missing=missing):
                    result = subprocess.run([ROOT / "scripts/test/smoke.sh"], cwd=directory,
                                            env={**env, missing: ""}, capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(captured.exists())
                    self.assertFalse(helper_marker.exists())
