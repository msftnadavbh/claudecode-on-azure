from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


VALIDATE = Path(__file__).with_name("validate.sh").read_text()
START = VALIDATE.rindex("scan_status=0")
SCANNER = VALIDATE[START:VALIDATE.index('\necho "Validation checks passed."', START)]
ROOTS = ("README.md", "CLAUDE.md", "docs", "infra", "apim", "scripts", "migration", ".github")


def marker(*parts):
    # Split synthetic forbidden literals so this test remains safe to scan itself.
    return "".join(parts)


class CredentialScanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ROOTS:
            path = self.root / name
            if path.suffix == ".md":
                path.write_text("safe\n")
            else:
                path.mkdir()
                (path / "safe.txt").write_text("safe\n")

    def scan(self):
        return subprocess.run(
            ["bash", "-c", "set -euo pipefail\n" + SCANNER], cwd=self.root, capture_output=True, text=True
        )

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
        return name

    def assert_clean(self):
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((result.stdout, result.stderr), ("", ""))

    def assert_rejected(self, name):
        result = self.scan()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines(), [name])
        self.assertEqual(result.stderr, "Forbidden production credential pattern found\n")
        return result

    def test_clean_tree_allowed(self):
        self.assert_clean()

    def test_bytecode_cache_allowed(self):
        self.write("scripts/__pycache__/bad.pyc", marker("list", "Secrets").encode())
        self.assert_clean()

    def test_legacy_bytecode_allowed(self):
        value = marker("Ocp", "-Apim-Subscription-Key:").encode()
        self.write("scripts/bad.pyc", value)
        self.write("scripts/bad.pyo", value)
        self.assert_clean()

    def test_python_test_source_rejected(self):
        name = self.write("scripts/test/test_bad.py", marker("list", "Secrets"))
        self.assert_rejected(name)

    def test_terraform_source_rejected(self):
        name = self.write("infra/tofu/bad.tf", marker("BEGIN ", "PRIVATE KEY"))
        self.assert_rejected(name)

    def test_credential_value_is_never_logged(self):
        secret = marker("fabricated-", "credential-value")
        assignment = marker("ANTHROPIC_", "API_KEY", "=", secret)
        name = self.write(".github/workflows/bad.yml", assignment)
        result = self.assert_rejected(name)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_nul_containing_source_rejected(self):
        value = marker("BEGIN ", "OPENSSH ", "PRIVATE KEY").encode()
        name = self.write("docs/bad.bin", b"\0" + value)
        self.assert_rejected(name)

    def test_missing_required_root_is_scan_error(self):
        shutil.rmtree(self.root / "docs")
        result = self.scan()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Credential scan failed", result.stderr)
        self.assertNotIn("Forbidden production credential pattern found", result.stderr)


if __name__ == "__main__":
    unittest.main()
