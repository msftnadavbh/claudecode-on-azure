#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts/claude_code"))
from generate_managed_settings import PLATFORM_PATHS, write_outputs


class ClaudeCodeManagedSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.args = argparse.Namespace(
            gateway_url="https://gateway.example/claude",
            audience="api://gateway-app-id",
            tenant_id="11111111-1111-1111-1111-111111111111",
            macos_helper_path="/Library/Company/Claude/apim-user-token-helper.sh",
            linux_helper_path="/opt/company/claude/apim-user-token-helper.sh",
            windows_helper_path=r"C:\ProgramData\Company\Claude\apim-user-token-helper.windows.cmd",
            opus_model="opus-pinned",
            sonnet_model="sonnet-pinned",
            haiku_model="haiku-pinned",
            output_dir=self.directory.name,
        )

    def test_semantic_settings(self) -> None:
        outputs = write_outputs(self.args)
        settings = json.loads(outputs["linux"].read_text(encoding="utf-8"))

        self.assertEqual(settings["apiKeyHelper"], shlex.quote(self.args.linux_helper_path))
        self.assertEqual(settings["env"], {
            "ANTHROPIC_BASE_URL": self.args.gateway_url,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku-pinned",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus-pinned",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet-pinned",
            "APIM_AUDIENCE": self.args.audience,
            "APIM_TENANT_ID": self.args.tenant_id,
            "CLAUDE_CODE_API_KEY_HELPER_TTL_MS": "300000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1",
        })

    def test_output_paths_and_encoding(self) -> None:
        outputs = write_outputs(self.args)
        self.assertEqual(set(outputs), set(PLATFORM_PATHS))
        self.assertEqual(PLATFORM_PATHS, {
            "macos": "/Library/Application Support/ClaudeCode/managed-settings.json",
            "linux": "/etc/claude-code/managed-settings.json",
            "windows": r"C:\Program Files\ClaudeCode\managed-settings.json",
        })
        for platform, path in outputs.items():
            self.assertEqual(path.relative_to(self.directory.name), Path(platform) / "managed-settings.json")
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(json.loads(raw.decode("utf-8"))["env"]["APIM_TENANT_ID"], self.args.tenant_id)
        self.assertEqual(json.loads(outputs["macos"].read_text(encoding="utf-8"))["apiKeyHelper"], shlex.quote(self.args.macos_helper_path))
        self.assertEqual(json.loads(outputs["windows"].read_text(encoding="utf-8"))["apiKeyHelper"], self.args.windows_helper_path)

    def test_posix_helper_is_one_literal_shell_command(self):
        marker = Path(self.directory.name) / "side-effect"
        helper = Path(self.directory.name) / "helper's $(touch side-effect); script.sh"
        helper.write_text('#!/bin/sh\nprintf "literal-helper\\n"\n')
        helper.chmod(0o700)
        for platform in ("macos", "linux"):
            setattr(self.args, f"{platform}_helper_path", str(helper))
        outputs = write_outputs(self.args)
        for platform in ("macos", "linux"):
            command = json.loads(outputs[platform].read_text())["apiKeyHelper"]
            self.assertEqual(shlex.split(command), [str(helper)])
            result = subprocess.run(["/bin/sh", "-c", command], cwd=self.directory.name,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, "literal-helper\n")
            self.assertFalse(marker.exists())

    def test_unsafe_windows_paths_rejected_before_output(self):
        for path in (r"C:\Program Files\helper.cmd", r"C:\foo&bar\helper.cmd", r"C:\foo%PATH%\helper.cmd",
                     r'C:\foo"bar\helper.cmd', "C:\\foo\\helper.cmd\n", r"\\server\share\helper.cmd",
                     r"\\?\C:\helper.cmd", r"C:relative\helper.cmd", r"C:\foo\..\helper.cmd",
                     r"C:\foo\.\helper.cmd", r"C:\foo.\helper.cmd", r"C:\CON\helper.cmd"):
            with self.subTest(path=path):
                self.args.windows_helper_path = path
                with self.assertRaises(ValueError):
                    write_outputs(self.args)
                self.assertEqual(list(Path(self.directory.name).glob("*/managed-settings.json")), [])

    def test_windows_normalizes_safe_slashes(self):
        self.args.windows_helper_path = "C:/ProgramData/Company/helper.cmd"
        outputs = write_outputs(self.args)
        self.assertEqual(json.loads(outputs["windows"].read_text())["apiKeyHelper"], r"C:\ProgramData\Company\helper.cmd")

    def test_deploy_validate_job_installs_same_tofu_step_before_validation(self):
        step = "      - name: Install OpenTofu\n        run: bash scripts/tofu/install.sh\n"
        deploy = (REPO_ROOT / ".github/workflows/deploy.yml").read_text().split("  plan:", 1)[0]
        validate = (REPO_ROOT / ".github/workflows/validate.yml").read_text().split("      - name: Write CI evidence", 1)[0]
        self.assertIn(step + "      - name: Validate repository\n        run: scripts/test/validate.sh", deploy)
        self.assertIn(step + "      - name: Validate repository\n        run: scripts/test/validate.sh", validate)

    def test_outputs_contain_no_static_credential_or_foundry_mode(self) -> None:
        outputs = write_outputs(self.args)
        content = "\n".join(path.read_text(encoding="utf-8").lower() for path in outputs.values())
        for forbidden in ("anthropic_api_key", "anthropic_auth_token", "foundry", "claude_code_use_foundry", "anthropic_foundry_base_url"):
            self.assertNotIn(forbidden, content)

    def test_requires_canonical_tenant_uuid(self):
        for tenant in ("", "tenant", "11111111111111111111111111111111", "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA", " 11111111-1111-1111-1111-111111111111"):
            with self.subTest(tenant=tenant):
                self.args.tenant_id = tenant
                with self.assertRaises(ValueError):
                    write_outputs(self.args)


if __name__ == "__main__":
    unittest.main()
