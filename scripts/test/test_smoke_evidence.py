#!/usr/bin/env python3
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy.yml"


def workflow_block(header, indent, text=None):
    lines = (WORKFLOW.read_text() if text is None else text).splitlines()
    start = lines.index(header)
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or len(lines[end]) - len(lines[end].lstrip()) > indent):
        end += 1
    return lines[start:end]


def workflow_run(name, text=None):
    step = workflow_block(f"      - name: {name}", 6, text)
    run = step.index("        run: |")
    body = []
    for line in step[run + 1:]:
        if line.strip() and not line.startswith("          "):
            raise ValueError(f"unexpected workflow run indentation: {line!r}")
        body.append(line[10:] if line else "")
    return "\n".join(body)


class SmokeEvidenceTests(unittest.TestCase):
    def run_case(self, attempts):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner_temp = root / "runner"
            smoke_dir = root / "scripts/test"
            bin_dir = root / "bin"
            state = root / "state"
            for directory in (runner_temp, smoke_dir, bin_dir, state):
                directory.mkdir(parents=True, exist_ok=True)
            for number, (code, stdout, stderr) in enumerate(attempts, 1):
                (state / f"status-{number}").write_text(str(code))
                if stdout is not None:
                    (state / f"stdout-{number}").write_text(stdout)
                if stderr is not None:
                    (state / f"stderr-{number}").write_text(stderr)
            smoke = smoke_dir / "smoke.sh"
            smoke.write_text("""#!/usr/bin/env bash
set -euo pipefail
count=0
[[ ! -f \"${FAKE_STATE}/count\" ]] || count=$(<\"${FAKE_STATE}/count\")
((count += 1))
printf '%s' \"${count}\" > \"${FAKE_STATE}/count\"
[[ ! -f \"${FAKE_STATE}/stdout-${count}\" ]] || while IFS= read -r line || [[ -n \"${line}\" ]]; do printf '%s\\n' \"${line}\"; done < \"${FAKE_STATE}/stdout-${count}\"
[[ ! -f \"${FAKE_STATE}/stderr-${count}\" ]] || while IFS= read -r line || [[ -n \"${line}\" ]]; do printf '%s\\n' \"${line}\" >&2; done < \"${FAKE_STATE}/stderr-${count}\"
exit \"$(<\"${FAKE_STATE}/status-${count}\")\"
""")
            smoke.chmod(0o700)
            sleep = bin_dir / "sleep"
            sleep.write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"${FAKE_STATE}/sleeps\"\n")
            sleep.chmod(0o700)
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c",
                 "umask 022\n" + workflow_run("Post-deployment smoke test")],
                cwd=root,
                env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
                     "RUNNER_TEMP": str(runner_temp), "FAKE_STATE": str(state)},
                capture_output=True,
                text=True,
            )
            evidence = runner_temp / "smoke-evidence.json"
            return {
                "result": result,
                "evidence": evidence.read_bytes(),
                "mode": stat.S_IMODE(evidence.stat().st_mode),
                "invocations": int((state / "count").read_text()),
                "sleeps": (state / "sleeps").read_text().splitlines() if (state / "sleeps").exists() else [],
            }

    def assert_case(self, attempts, code, invocations, sleeps, final):
        observed = self.run_case(attempts)
        self.assertEqual(observed["result"].returncode, code)
        self.assertEqual(observed["invocations"], invocations)
        self.assertEqual(observed["sleeps"], ["30"] * sleeps)
        self.assertEqual(observed["mode"], 0o600)
        self.assertEqual(json.loads(observed["evidence"]), final)
        return observed

    def test_immediate_success(self):
        final = {"attempt": 1, "ok": True}
        self.assert_case([(0, json.dumps(final), None)], 0, 1, 0, final)

    def test_failures_then_success_retains_only_success(self):
        attempts = [(1, json.dumps({"attempt": number, "ok": False}), None) for number in (1, 2)]
        final = {"attempt": 3, "ok": True}
        self.assert_case(attempts + [(0, json.dumps(final), None)], 0, 3, 2, final)

    def test_six_failures_retains_final_failure(self):
        attempts = [(1, json.dumps({"attempt": number, "ok": False}), None) for number in range(1, 7)]
        self.assert_case(attempts, 1, 6, 5, {"attempt": 6, "ok": False})

    def test_final_empty_stdout_clears_prior_evidence(self):
        attempts = [(1, json.dumps({"attempt": number, "ok": False}), None) for number in range(1, 6)]
        observed = self.run_case(attempts + [(1, None, None)])
        self.assertEqual(observed["result"].returncode, 1)
        self.assertEqual(observed["invocations"], 6)
        self.assertEqual(observed["sleeps"], ["30"] * 5)
        self.assertEqual(observed["evidence"], b"")

    def test_stderr_is_not_evidence(self):
        final = {"attempt": 1, "ok": True}
        observed = self.assert_case([(0, json.dumps(final), "private diagnostic")], 0, 1, 0, final)
        self.assertIn("private diagnostic", observed["result"].stderr)
        self.assertNotIn(b"private diagnostic", observed["evidence"])

    def test_upload_runs_always_without_failure_suppression(self):
        smoke = "\n".join(workflow_block("      - name: Post-deployment smoke test", 6))
        upload = "\n".join(workflow_block("      - name: Upload smoke evidence", 6))
        smoke_job = "\n".join(workflow_block("  smoke:", 2))
        self.assertIn("        shell: bash", smoke)
        self.assertIn("        if: always()", upload)
        self.assertIn("uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", upload)
        self.assertIn("name: tofu-deploy-smoke-${{ github.sha }}-${{ github.run_id }}", upload)
        self.assertIn("path: ${{ runner.temp }}/smoke-evidence.json", upload)
        self.assertIn("if-no-files-found: error", upload)
        self.assertIn("retention-days: 90", upload)
        self.assertNotIn("continue-on-error:", smoke_job)
        self.assertNotIn("|| true", workflow_run("Post-deployment smoke test"))

    def test_workflow_run_rejects_malformed_indentation(self):
        malformed = "      - name: Post-deployment smoke test\n        run: |\n        umask 077\n"
        with self.assertRaises(ValueError):
            workflow_run("Post-deployment smoke test", malformed)


if __name__ == "__main__":
    unittest.main()
