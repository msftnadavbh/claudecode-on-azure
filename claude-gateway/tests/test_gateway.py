"""Offline POC contract tests; no Azure credentials or real secrets."""

import copy
import hashlib
import importlib.util
import io
import ipaddress
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("configure", ROOT / "configure.py")
configure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(configure)


def settings():
    return {
        "public_url": "https://gateway.pilot.internal:8443",
        "tenant_id": "11111111-2222-4333-8444-555555555555",
        "client_id": "66666666-7777-4888-8999-aaaaaaaaaaaa",
        "groups_claim": "groups",
        "allowed_groups": ["bbbbbbbb-cccc-4ddd-8eee-ffffffffffff"],
        "foundry_resource": "pilot-foundry",
        "models": [
            {"id": "claude-sonnet-4-6", "deployment": "pilot-sonnet"},
            {"id": "claude-haiku-4-5", "deployment": "pilot-haiku"},
        ],
        "claude_version": "2.1.296",
        "claude_sha256": hashlib.sha256(b"safe-test-fixture").hexdigest(),
        "signed_release_verified": True,
    }


class ConfigurationTests(unittest.TestCase):
    def test_valid_config_matches_documented_schema(self):
        config = configure.render(settings())
        self.assertEqual(set(config), {
            "listen", "oidc", "session", "store", "upstreams",
            "auto_include_builtin_models", "models", "managed",
        })
        self.assertEqual(config["listen"]["port"], 8443)
        self.assertEqual(config["oidc"]["issuer"],
                         "https://login.microsoftonline.com/11111111-2222-4333-8444-555555555555/v2.0")
        self.assertIn("offline_access", config["oidc"]["scopes"])
        self.assertEqual(config["session"]["ttl_hours"], 1)
        self.assertFalse(config["auto_include_builtin_models"])
        self.assertEqual(config["upstreams"], [{
            "name": "foundry", "provider": "foundry", "resource": "pilot-foundry",
            "auth": {"use_azure_ad": True},
        }])
        self.assertEqual(config["models"][0]["upstream_model"], {"foundry": "pilot-sonnet"})
        policy, fallback = config["managed"]["policies"]
        self.assertEqual(policy["match"]["groups"], config["oidc"]["allowed_groups"])
        self.assertEqual(policy["code"]["availableModels"], ["claude-sonnet-4-6", "claude-haiku-4-5"])
        self.assertEqual(policy["code"]["model"], "claude-sonnet-4-6")
        self.assertTrue(policy["code"]["enforceAvailableModels"])
        self.assertEqual(fallback, {"match": {}, "code": {"availableModels": []}})
        self.assertEqual(policy["code"]["env"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"], "1")

    def test_secret_references_and_no_telemetry_or_admin(self):
        config = configure.render(settings())
        for block, key, filename in (
            ("oidc", "client_secret", "oidc-secret"),
            ("session", "jwt_secret", "session-secret"),
            ("store", "password", "database-secret"),
        ):
            self.assertEqual(config[block][key], "${file:/etc/claude-gateway/" + filename + "}")
        self.assertNotIn("@", config["store"]["postgres_url"])
        self.assertNotIn("telemetry", config)
        self.assertNotIn("admin", config)

    def test_example_is_not_deployable_without_confirmation(self):
        with self.assertRaises(ValueError):
            configure.validate(json.loads((ROOT / "settings.example.json").read_text()))

    def test_rejects_invalid_inputs(self):
        cases = {
            "public_url": [
                "http://gateway.pilot.internal:8443", "https://gateway.pilot.internal",
                "https://gateway.pilot.internal:8443/", "https://gateway.example.com:8443",
                "https://user@gateway.pilot.internal:8443", "https://gateway.pilot.internal:8443?x=y",
                "https://localhost:8443",
            ],
            "tenant_id": ["", "common", "00000000-0000-0000-0000-000000000000"],
            "client_id": ["REPLACE_ME", "${CLIENT_ID}"],
            "allowed_groups": [[], [""], ["engineering"], ["${GROUP}"]],
            "groups_claim": ["email", "Groups"],
            "foundry_resource": ["https://foundry.services.ai.azure.com", "CHANGEME"],
            "models": [[], [{"id": "sonnet", "deployment": "pilot"}],
                       [{"id": "claude-sonnet-4-6", "deployment": "${DEPLOYMENT}"}]],
            "claude_version": ["2.1.195", "2.1.295", "latest", "2.1.296-beta"],
            "claude_sha256": ["0" * 64, "bad", "A" * 64],
            "signed_release_verified": [False, "true", 1],
        }
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    candidate = settings()
                    candidate[key] = value
                    with self.assertRaises((ValueError, TypeError)):
                        configure.validate(candidate)

    def test_rejects_unknown_keys_and_duplicate_ids(self):
        candidate = settings()
        candidate["api_key"] = "not-a-real-secret"
        with self.assertRaises(ValueError):
            configure.validate(candidate)
        candidate = settings()
        candidate["models"].append(copy.deepcopy(candidate["models"][0]))
        with self.assertRaises(ValueError):
            configure.validate(candidate)
        candidate = settings()
        candidate["allowed_groups"] *= 2
        with self.assertRaises(ValueError):
            configure.validate(candidate)

    def test_app_roles(self):
        candidate = settings()
        candidate.update(groups_claim="roles", allowed_groups=["Gateway.Pilot"])
        self.assertEqual(configure.render(candidate)["oidc"]["allowed_groups"], ["Gateway.Pilot"])

    def test_dns_rejects_any_nonprivate_address(self):
        for addresses, accepted in [
            (["10.1.2.3"], True), (["172.16.0.1", "192.168.1.1"], True),
            (["10.1.2.3", "8.8.8.8"], False), (["127.0.0.1"], False),
            (["169.254.169.254"], False), (["::1"], False), (["fc00::1"], False),
            (["172.32.1.1"], False), ([], False),
        ]:
            with self.subTest(addresses=addresses):
                answers = [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 8443))
                    for address in addresses
                ]
                with patch.object(configure.socket, "getaddrinfo", return_value=answers):
                    if accepted:
                        configure.private_dns("gateway.pilot.internal")
                    else:
                        with self.assertRaises(ValueError):
                            configure.private_dns("gateway.pilot.internal")

    def test_binary_verification(self):
        header = b"\x7fELF\x02\x01" + b"\x00" * 12 + b"\x3e\x00"
        data = header + b"fake-not-executable"
        digest = hashlib.sha256(data).hexdigest()
        with patch.object(Path, "open", return_value=io.BytesIO(data)):
            configure.verify_binary("in-memory-fixture", digest)
        with patch.object(Path, "open", return_value=io.BytesIO(data)):
            with self.assertRaises(ValueError):
                configure.verify_binary("in-memory-fixture", "0" * 64)
        data = b"#!/bin/sh\nexit 0\n"
        with patch.object(Path, "open", return_value=io.BytesIO(data)):
            with self.assertRaises(ValueError):
                configure.verify_binary("in-memory-fixture", hashlib.sha256(data).hexdigest())

    def test_cli_rejects_example_without_output(self):
        result = subprocess.run(
            ["python3", str(ROOT / "configure.py"), str(ROOT / "settings.example.json")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("Configuration rejected", result.stderr)


class IsolationTests(unittest.TestCase):
    def test_infrastructure_is_additive_and_private(self):
        main = (ROOT / "main.tf").read_text()
        self.assertNotIn("azurerm_public_ip", main)
        self.assertNotIn("custom_data", main)
        self.assertNotIn("remote_state", main)
        self.assertIn('backend "local"', main)
        self.assertIn('path = "claude-gateway.tfstate"', main)
        self.assertIn('version = "= 4.56.0"', main)
        self.assertIn('required_version = "= 1.12.3"', main)
        self.assertIn('name                       = "deny-other-inbound"', main)
        self.assertIn('destination_port_range     = "8443"', main)
        self.assertIn('destination_port_range     = "22"', main)
        self.assertNotIn('destination_port_range     = "5432"', main)
        self.assertIn('type = "SystemAssigned"', main)
        self.assertIn("53ca6127-db72-4b80-b1b0-d745d6d5456d", main)
        self.assertIn("scope                            = var.foundry_resource_id", main)
        self.assertNotIn('resource "azurerm_subnet"', main)

    def test_service_is_unprivileged_and_uses_native_gateway(self):
        service = (ROOT / "claude-gateway.service").read_text()
        self.assertIn("User=claude-gateway", service)
        self.assertIn("ExecStart=/usr/bin/env -i ", service)
        self.assertIn(" gateway --config /etc/claude-gateway/gateway.yaml", service)
        self.assertIn("ProtectSystem=strict", service)
        self.assertIn("ProtectHome=true", service)
        self.assertIn("PrivateTmp=true", service)
        self.assertIn("LimitCORE=0", service)
        self.assertNotIn("PrivateNetwork", service)  # IMDS must remain reachable.
        self.assertNotIn("AZURE_CLIENT_SECRET", service)
        self.assertNotIn("ANTHROPIC_API_KEY", service)

    def test_installer_private_database_and_secrets(self):
        installer = (ROOT / "install.sh").read_text()
        self.assertIn("listen_addresses = '127.0.0.1'", installer)
        self.assertIn("scram-sha-256", installer)
        self.assertIn("--check-dns", installer)
        self.assertIn("--binary", installer)
        self.assertIn("INSTALL-ISOLATED-POC", installer)
        self.assertIn("missing prerequisite", installer)
        self.assertIn("package directory must be root-owned mode 0700", installer)
        self.assertIn("openssl rand -hex 32", installer)
        self.assertIn("systemctl disable --now claude-gateway", installer)
        self.assertNotIn("curl |", installer)
        self.assertNotIn("curl -k", installer)
        self.assertNotIn("set -x", installer)

    def test_example_cidrs_are_private(self):
        for network in ["10.20.30.0/24", "10.20.40.5/32"]:
            self.assertTrue(ipaddress.ip_network(network).is_private)

    def test_postgres_can_read_both_configs_before_start(self):
        installer = (ROOT / "install.sh").read_text()
        configs = "/etc/postgresql/16/main/{conf.d/claude-gateway.conf,pg_hba.conf}"
        ownership = f"chown root:postgres {configs}"
        permissions = f"chmod 0640 {configs}"
        self.assertIn(ownership, installer)
        self.assertIn(permissions, installer)
        self.assertLess(installer.index("host all all ::/0 reject"), installer.index(ownership))
        self.assertLess(installer.index(ownership), installer.index(permissions))
        self.assertLess(installer.index(permissions), installer.index("systemctl enable --now postgresql"))


if __name__ == "__main__":
    unittest.main()
