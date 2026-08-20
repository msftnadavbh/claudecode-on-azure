#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "scripts/auth/apim-user-token-helper.sh"
ENV_HELPER = REPO_ROOT / "scripts/auth/print-claude-env.sh"


class AuthHelperTests(unittest.TestCase):
    def test_helper_refreshes_without_persisting_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_az = root / "az"
            counter = root / "counter"
            fake_az.write_text(
                "#!/usr/bin/env bash\n"
                "count=$(($(cat \"$COUNTER\" 2>/dev/null || echo 0) + 1))\n"
                "printf '%s' \"$count\" > \"$COUNTER\"\n"
                "printf 'token-%s\\n' \"$count\"\n"
            )
            fake_az.chmod(0o700)
            env = {
                **os.environ,
                "PATH": f"{root}:{os.environ['PATH']}",
                "COUNTER": str(counter),
                "HOME": str(root),
                "APIM_AUDIENCE": "api://test-gateway",
            }
            first = subprocess.check_output([HELPER], env=env, text=True).strip()
            second = subprocess.check_output([HELPER], env=env, text=True).strip()
            self.assertEqual(first, "Bear" + "er token-1")
            self.assertEqual(second, "Bear" + "er token-2")
            self.assertNotIn("token-1", "\n".join(p.read_text() for p in root.rglob("*") if p.is_file() and p != counter and p != fake_az))

    def test_production_environment_is_gateway_mode_and_scrubbed(self) -> None:
        env = {
            **os.environ,
            "APIM_BASE_URL": "https://gateway.example/claude",
            "APIM_AUDIENCE": "api://gateway",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus-pinned",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet-pinned",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku-pinned",
        }
        output = subprocess.check_output([ENV_HELPER, "prod"], env=env, text=True)
        self.assertIn("ANTHROPIC_BASE_URL=", output)
        self.assertNotIn("ANTHROPIC_FOUNDRY_BASE_URL", output)
        self.assertIn("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1", output)
        for model in ("opus-pinned", "sonnet-pinned", "haiku-pinned"):
            self.assertIn(model, output)


if __name__ == "__main__":
    unittest.main()
