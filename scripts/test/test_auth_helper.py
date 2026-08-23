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
            self.assertEqual(first, "token-1")
            self.assertEqual(second, "token-2")
            self.assertFalse(first.startswith("Bearer "))
            self.assertFalse(second.startswith("Bearer "))
            self.assertNotIn("token-1", "\n".join(p.read_text() for p in root.rglob("*") if p.is_file() and p != counter and p != fake_az))

if __name__ == "__main__":
    unittest.main()
