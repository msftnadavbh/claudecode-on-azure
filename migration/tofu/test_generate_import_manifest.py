#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_import_manifest


SUBSCRIPTION = "11111111-1111-1111-1111-111111111111"
GUIDS = {
    "primary-foundry": "22222222-2222-2222-2222-222222222222",
    "secondary-foundry": "33333333-3333-3333-3333-333333333333",
    "primary-monitoring": "44444444-4444-4444-4444-444444444444",
    "secondary-monitoring": "55555555-5555-5555-5555-555555555555",
}


def account_id(name):
    return f"/subscriptions/{SUBSCRIPTION}/resourceGroups/foundry-rg/providers/Microsoft.CognitiveServices/accounts/{name}"


class ImportManifestTests(unittest.TestCase):
    def generate(self, extra):
        with tempfile.TemporaryDirectory() as directory:
            shell, manifest = Path(directory, "imports.sh"), Path(directory, "imports.json")
            args = [
                "--subscription", SUBSCRIPTION, "--resource-group", "gateway-rg", "--primary-apim", "gateway-primary",
                "--primary-foundry-account-id", account_id("foundry-primary"),
                "--primary-foundry-role-assignment", GUIDS["primary-foundry"],
                "--var-file", "reviewed.tfvars.json",
                "--shell-output", str(shell), "--json-output", str(manifest), *extra,
            ]
            self.assertEqual(generate_import_manifest.main(args), 0)
            return json.loads(manifest.read_text()), shell.read_text()

    def test_single_region_minimal(self):
        manifest, shell = self.generate([])
        self.assertEqual(len(manifest["imports"]), 24)
        self.assertEqual(len(manifest["excluded"]), 1)
        self.assertIn('azapi_resource.apim["primary"]', {item["address"] for item in manifest["imports"]})
        ids = {item["address"]: item["id"] for item in manifest["imports"]}
        self.assertTrue(ids['azapi_resource.apim["primary"]'].endswith("?api-version=2025-03-01-preview"))
        self.assertTrue(ids['azurerm_api_management_api.claude["primary"]'].endswith("/apis/claude;rev=1"))
        self.assertIn("tofu -chdir=infra/tofu import -input=false -var-file=reviewed.tfvars.json", shell)
        self.assertIn("azapi_resource.apim", shell)
        self.assertNotIn("azurerm_monitor_metric_alert", shell)

    def test_dual_region_full(self):
        manifest, shell = self.generate([
            "--secondary-apim", "gateway-secondary", "--secondary-foundry-account-id", account_id("foundry-secondary"),
            "--secondary-foundry-role-assignment", GUIDS["secondary-foundry"],
            "--observability", "managed", "--workspace-name", "gateway-logs", "--app-insights-name", "gateway-insights",
            "--primary-monitoring-role-assignment", GUIDS["primary-monitoring"],
            "--secondary-monitoring-role-assignment", GUIDS["secondary-monitoring"],
            "--traffic-manager-name", "gateway-failover",
        ])
        self.assertEqual(len(manifest["imports"]), 71)
        self.assertEqual(sum("metric_alert" in item["address"] for item in manifest["imports"]), 10)
        addresses = {item["address"] for item in manifest["imports"]}
        self.assertIn('azurerm_monitor_metric_alert.cpu["primary"]', addresses)
        self.assertIn('azurerm_monitor_metric_alert.memory["primary"]', addresses)
        self.assertIn('azurerm_monitor_metric_alert.requests["primary"]', addresses)
        self.assertIn("azurerm_traffic_manager_external_endpoint.apim", shell)


if __name__ == "__main__":
    unittest.main()
