#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import plistlib
import re
import subprocess
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

    def test_discovery_omits_fixed_list_and_deletes_it_in_selected_windows_scope(self):
        legacy = build_settings(self.args)
        self.args.enable_model_discovery = True
        for scope in ("machine", "user"):
            with self.subTest(scope=scope):
                self.args.windows_scope = scope
                macos, windows, removal = write_outputs(self.args)
                settings = build_settings(self.args)
                expected = {**legacy, "modelDiscoveryEnabled": "true"}
                expected.pop("inferenceModels")
                self.assertEqual(settings, expected)
                profile_settings = plistlib.loads(macos.read_bytes())["PayloadContent"][0]["PayloadContent"]["com.anthropic.claudefordesktop"]["Forced"][0]["mcx_preference_settings"]
                self.assertEqual(profile_settings, settings)
                lines = windows.read_bytes().decode("utf-16").splitlines()
                hive = "HKEY_LOCAL_MACHINE" if scope == "machine" else "HKEY_CURRENT_USER"
                self.assertEqual(lines[2], f"[{hive}\\SOFTWARE\\Policies\\Claude]")
                self.assertEqual(lines.count('"inferenceModels"=-'), 1)
                existing = {**legacy, "UnrelatedPolicy": "keep"}
                for line in lines[3:]:
                    key, value = line.split("=", 1)
                    if value == "-":
                        existing.pop(json.loads(key), None)
                    else:
                        existing[json.loads(key)] = json.loads(value)
                self.assertEqual(existing, {**settings, "UnrelatedPolicy": "keep"})
                remove_lines = removal.read_bytes().decode("utf-16").splitlines()
                self.assertEqual(remove_lines[2], lines[2])
                self.assertEqual(set(remove_lines[3:]), {f'"{key}"=-' for key in legacy})
                self.assertFalse(any(line.startswith("[-") for line in remove_lines))
                for line in remove_lines[3:]:
                    existing.pop(json.loads(line[:-2]), None)
                self.assertEqual(existing, {"UnrelatedPolicy": "keep"})
                for path in (windows, removal):
                    self.assertTrue(path.read_bytes().startswith(b"\xff\xfe"))
                    self.assertNotIn("\n", path.read_bytes().decode("utf-16").replace("\r\n", ""))

    def test_cli_discovery_opt_in(self):
        arguments = [sys.executable, "-B", str(REPO_ROOT / "scripts/desktop/generate_managed_config.py")]
        for name, value in vars(self.args).items():
            if name != "disable_cowork":
                arguments.extend(["--" + name.replace("_", "-"), value])
        result = subprocess.run(arguments + ["--enable-model-discovery"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        windows = (Path(self.directory.name) / "claude-desktop-managed.reg").read_bytes().decode("utf-16")
        self.assertIn('"modelDiscoveryEnabled"="true"', windows)
        self.assertIn('"inferenceModels"=-', windows)

    def test_discovery_cli_needs_no_unused_model_pins(self):
        arguments = [sys.executable, "-B", str(REPO_ROOT / "scripts/desktop/generate_managed_config.py")]
        for name, value in vars(self.args).items():
            if name != "disable_cowork" and not name.endswith("_model"):
                arguments.extend(["--" + name.replace("_", "-"), value])
        missing = subprocess.run(arguments, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("required unless --enable-model-discovery", missing.stderr)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])
        result = subprocess.run(arguments + ["--enable-model-discovery"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        profile = plistlib.loads((Path(self.directory.name) / "claude-desktop-managed.mobileconfig").read_bytes())
        settings = profile["PayloadContent"][0]["PayloadContent"]["com.anthropic.claudefordesktop"]["Forced"][0]["mcx_preference_settings"]
        self.assertEqual(settings["modelDiscoveryEnabled"], "true")
        self.assertNotIn("inferenceModels", settings)
        self.assertEqual(settings["inferenceProvider"], "gateway")

    def test_each_static_model_pin_remains_required(self):
        for family in ("sonnet", "opus", "haiku"):
            with self.subTest(family=family):
                args = argparse.Namespace(**vars(self.args))
                setattr(args, f"{family}_model", None)
                with self.assertRaisesRegex(ValueError, f"--{family}-model is required"):
                    write_outputs(args)
                self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_macos_profile_identity_survives_discovery_and_rollback(self):
        macos, _, _ = write_outputs(self.args)
        original = plistlib.loads(macos.read_bytes())
        self.args.enable_model_discovery = True
        write_outputs(self.args)
        discovered = plistlib.loads(macos.read_bytes())
        for key in ("PayloadUUID", "PayloadIdentifier", "PayloadScope"):
            self.assertEqual(discovered[key], original[key])
        for key in ("PayloadUUID", "PayloadIdentifier", "PayloadType"):
            self.assertEqual(discovered["PayloadContent"][0][key], original["PayloadContent"][0][key])
        self.args.enable_model_discovery = False
        write_outputs(self.args)
        self.assertEqual(plistlib.loads(macos.read_bytes()), original)


if __name__ == "__main__":
    unittest.main()
