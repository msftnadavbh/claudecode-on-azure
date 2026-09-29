#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "scripts/auth/apim-user-token-helper.sh"


class AuthHelperTests(unittest.TestCase):
    def test_helper_refreshes_without_persisting_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_az = root / "az"
            counter = root / "counter"
            fake_az.write_text(
                "#!/usr/bin/env bash\n"
                "expected=(account get-access-token --tenant 11111111-1111-1111-1111-111111111111 --resource api://test-gateway --query accessToken --output tsv)\n"
                "[[ $# == ${#expected[@]} ]] || exit 9\n"
                "for arg in \"${expected[@]}\"; do [[ $1 == \"$arg\" ]] || exit 9; shift; done\n"
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
                "APIM_TENANT_ID": "11111111-1111-1111-1111-111111111111",
            }
            first = subprocess.check_output([HELPER], env=env, text=True).strip()
            second = subprocess.check_output([HELPER], env=env, text=True).strip()
            self.assertEqual(first, "token-1")
            self.assertEqual(second, "token-2")
            self.assertFalse(first.startswith("Bearer "))
            self.assertFalse(second.startswith("Bearer "))
            self.assertNotIn("token-1", "\n".join(p.read_text() for p in root.rglob("*") if p.is_file() and p != counter and p != fake_az))

    def test_fixed_failure_and_malformed_output_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "az"
            fake.write_text('#!/usr/bin/env bash\nprintf "%s" "$FAKE_OUTPUT"\nprintf "sensitive-stderr" >&2\nexit "$FAKE_STATUS"\n')
            fake.chmod(0o700)
            env = {**os.environ, "PATH": f"{root}:{os.environ['PATH']}",
                   "APIM_AUDIENCE": "api://test-gateway", "APIM_TENANT_ID": "11111111-1111-1111-1111-111111111111"}
            for output, status in [("", "0"), ("null\n", "0"), (" \t\n", "0"),
                                   ("sensitive\nsecond\n", "0"), ("sensitive\n\n", "0"),
                                   ("sensitive token\n", "0"), ("sensitive\n", "1")]:
                with self.subTest(output=output):
                    result = subprocess.run([HELPER], env={**env, "FAKE_OUTPUT": output, "FAKE_STATUS": status}, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "Unable to acquire access token\n")
            for name in ("APIM_AUDIENCE", "APIM_TENANT_ID"):
                result = subprocess.run([HELPER], env={**env, name: "", "FAKE_OUTPUT": "sensitive", "FAKE_STATUS": "0"}, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "APIM_AUDIENCE and APIM_TENANT_ID must be set\n")

if __name__ == "__main__":
    unittest.main()
