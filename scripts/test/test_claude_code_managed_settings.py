#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
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
            macos_helper_path="/Library/Company/Claude/apim-user-token-helper.sh",
            linux_helper_path="/opt/company/claude/apim-user-token-helper.sh",
            windows_helper_path=r"C:\Program Files\Company\Claude\apim-user-token-helper.cmd",
            opus_model="opus-pinned",
            sonnet_model="sonnet-pinned",
            haiku_model="haiku-pinned",
            output_dir=self.directory.name,
        )

    def test_semantic_settings(self) -> None:
        outputs = write_outputs(self.args)
        settings = json.loads(outputs["linux"].read_text(encoding="utf-8"))

        self.assertEqual(settings["apiKeyHelper"], self.args.linux_helper_path)
        self.assertEqual(settings["env"], {
            "ANTHROPIC_BASE_URL": self.args.gateway_url,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku-pinned",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus-pinned",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet-pinned",
            "APIM_AUDIENCE": self.args.audience,
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
            json.loads(raw.decode("utf-8"))
        self.assertEqual(json.loads(outputs["macos"].read_text(encoding="utf-8"))["apiKeyHelper"], self.args.macos_helper_path)
        self.assertEqual(json.loads(outputs["windows"].read_text(encoding="utf-8"))["apiKeyHelper"], self.args.windows_helper_path)

    def test_outputs_contain_no_static_credential_or_foundry_mode(self) -> None:
        outputs = write_outputs(self.args)
        content = "\n".join(path.read_text(encoding="utf-8").lower() for path in outputs.values())
        for forbidden in ("anthropic_api_key", "anthropic_auth_token", "foundry", "claude_code_use_foundry", "anthropic_foundry_base_url"):
            self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
