#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts/desktop"))
from generate_managed_config import write_outputs


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
            raw.decode("utf-16")

        outputs = macos.read_bytes().decode() + windows.read_bytes().decode("utf-16")
        lowered = outputs.lower()
        for forbidden in ("apikey", "api_key", "credentialhelper", "auth_token", "static credential"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("[-HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Claude]", removal.read_bytes().decode("utf-16"))


if __name__ == "__main__":
    unittest.main()
