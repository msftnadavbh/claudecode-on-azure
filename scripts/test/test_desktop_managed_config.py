#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import plistlib
import re
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts/desktop"))
from generate_managed_config import build_settings, write_outputs


class DesktopManagedConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.args = argparse.Namespace(
            gateway_url="https://gateway.example/claude",
            tenant_id="11111111-1111-1111-1111-111111111111",
            desktop_client_id="22222222-2222-2222-2222-222222222222",
            delegated_scope="api://33333333-3333-3333-3333-333333333333/Claude.Access",
            deployment_org_id="44444444-4444-4444-4444-444444444444",
            organization="Example Corp",
            sonnet_model="sonnet-pinned",
            opus_model="opus-pinned",
            haiku_model="haiku-pinned",
            output_dir=self.directory.name,
            windows_scope="machine",
            disable_cowork=False,
        )

    def test_semantic_configuration(self) -> None:
        macos, _, _ = write_outputs(self.args)
        payload = plistlib.loads(macos.read_bytes())["PayloadContent"][0]
        self.assertEqual(payload["PayloadType"], "com.apple.ManagedClient.preferences")
        settings = payload["PayloadContent"]["com.anthropic.claudefordesktop"]["Forced"][0]["mcx_preference_settings"]
        oidc = json.loads(settings["inferenceGatewayOidc"])
        models = json.loads(settings["inferenceModels"])

        self.assertEqual(oidc["bearerTokenType"], "access_token")
        self.assertIn(self.args.delegated_scope, oidc["scopes"].split())
        self.assertEqual({model["anthropicFamilyTier"]: model["name"] for model in models}, {
            "haiku": "haiku-pinned", "opus": "opus-pinned", "sonnet": "sonnet-pinned"
        })
        self.assertEqual(settings["disabledBuiltinTools"], '["WebSearch","WebFetch"]')
        self.assertEqual(settings["allowedWorkspaceFolders"], '[{"mode":"rw","path":"~/Documents/Claude"}]')
        self.assertEqual(settings["managedMcpServers"], "[]")
        for key in ("chatTabEnabled", "coworkTabEnabled", "isClaudeCodeForDesktopEnabled"):
            self.assertEqual(settings[key], "true")
        for key in ("modelDiscoveryEnabled", "toolSearchEnabled", "isLocalDevMcpEnabled", "isDesktopExtensionEnabled"):
            self.assertEqual(settings[key], "false")
        self.assertEqual(settings["coworkEgressAllowedHosts"], "[]")

    def test_output_encodings_and_no_credentials(self) -> None:
        macos, windows, removal = write_outputs(self.args)
        self.assertTrue(macos.read_bytes().startswith(b"<?xml"))
        for path in (windows, removal):
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xff\xfe"))
            text = raw.decode("utf-16")
            self.assertNotIn("\n", text.replace("\r\n", ""))

        outputs = macos.read_bytes().decode() + windows.read_bytes().decode("utf-16")
        lowered = outputs.lower()
        for forbidden in ("apikey", "api_key", "credentialhelper", "auth_token", "static credential"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("[HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Claude]", removal.read_bytes().decode("utf-16"))

    def test_windows_roundtrip_and_scoped_removal(self) -> None:
        self.args.organization = 'Exämple "Corp" \\ Division'
        self.args.sonnet_model = self.args.opus_model = self.args.haiku_model = "opus-5-5"
        self.args.windows_scope = "user"
        self.args.disable_cowork = True
        macos, windows, removal = write_outputs(self.args)
        settings = build_settings(self.args)
        lines = windows.read_bytes().decode("utf-16").splitlines()
        self.assertEqual(lines[2], r"[HKEY_CURRENT_USER\SOFTWARE\Policies\Claude]")
        entries = {}
        for line in lines[3:]:
            match = re.fullmatch(r'("(?:\\.|[^"\\])*")=("(?:\\.|[^"\\])*")', line)
            self.assertIsNotNone(match, line)
            entries[json.loads(match[1])] = json.loads(match[2])
        self.assertEqual(entries, settings)
        self.assertEqual(settings["coworkTabEnabled"], "false")
        models = json.loads(entries["inferenceModels"])
        self.assertEqual({model["anthropicFamilyTier"] for model in models}, {"opus", "sonnet", "haiku"})
        self.assertEqual([model["name"] for model in models], ["opus-5-5"] * 3)
        profile_settings = plistlib.loads(macos.read_bytes())["PayloadContent"][0]["PayloadContent"]["com.anthropic.claudefordesktop"]["Forced"][0]["mcx_preference_settings"]
        self.assertEqual(profile_settings["coworkTabEnabled"], "false")

        remove_lines = removal.read_bytes().decode("utf-16").splitlines()
        self.assertEqual(remove_lines[2], lines[2])
        self.assertEqual(set(remove_lines[3:]), {f'"{key}"=-' for key in settings})
        self.assertFalse(any(line.startswith("[-") for line in remove_lines))
        existing = {**entries, "UnrelatedPolicy": "keep"}
        for line in remove_lines[3:]:
            existing.pop(json.loads(line[:-2]), None)
        self.assertEqual(existing, {"UnrelatedPolicy": "keep"})

    def test_malformed_inputs_fail_before_writing(self) -> None:
        invalid = {
            "gateway_url": (
                "https://gateway.example/claude\r\n\"Injected\"=\"true\"",
                "https://@gateway.example/claude",
                "https://user:pass@gateway.example/claude",
                "https://gateway.example:invalid/claude",
                "https://gateway.example:65536/claude",
                "https://gateway.example/claude?debug=1",
            ),
            "delegated_scope": (
                "api://app/Claude.Access extra.scope",
                "api://app/Claude.Access\tother.scope",
                "api://app/Claude.Access?extra=scope",
                "api://app/Claude.Access#extra",
                "api://@app/Claude.Access",
                "https://user:pass@app/Claude.Access",
                "api://app:bad/Claude.Access",
            ),
            "organization": ("Unsafe\n\"Injected\"=\"true\"",),
            "opus_model": ("opus\x7fnot-a-model",),
        }
        for name, values in invalid.items():
            original = getattr(self.args, name)
            for value in values:
                with self.subTest(option=name, value=value):
                    setattr(self.args, name, value)
                    output = Path(self.directory.name) / "not-created"
                    self.args.output_dir = str(output)
                    with self.assertRaises(ValueError):
                        write_outputs(self.args)
                    self.assertFalse(output.exists())
            setattr(self.args, name, original)


if __name__ == "__main__":
    unittest.main()
