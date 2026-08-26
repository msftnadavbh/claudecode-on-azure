#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tofu"))
import generate_tfvars


ENV = {
    "ENVIRONMENT_PROFILE": "prod", "AZURE_RESOURCE_GROUP": "gateway-rg", "AZURE_LOCATION": "eastus",
    "APIM_NAME": "gateway", "APIM_PUBLISHER_EMAIL": "team@example.com", "APIM_PUBLISHER_NAME": "Team",
    "ENTRA_TENANT_ID": "11111111-1111-1111-1111-111111111111", "APIM_EXPECTED_AUDIENCE": "api://gateway",
    "APIM_REQUIRED_APP_ROLE": "Gateway.User", "FOUNDRY_BASE_URL": "https://foundry.services.ai.azure.com/anthropic",
    "FOUNDRY_SUBSCRIPTION_ID": "22222222-2222-2222-2222-222222222222", "FOUNDRY_RESOURCE_GROUP": "foundry-rg",
    "FOUNDRY_ACCOUNT_NAME": "foundry", "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus", "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku", "PER_USER_RATE_LIMIT": "100", "PER_USER_TOKEN_LIMIT": "50000",
    "APIM_DEFAULT_CAPACITY": "2", "PER_USER_CONCURRENT_STREAM_LIMIT": "20", "AGGREGATE_CONCURRENT_STREAM_LIMIT": "40",
}


class GenerateTfvarsTests(unittest.TestCase):
    def test_writes_typed_prod_values(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, ENV, clear=True):
            path = Path(directory) / "inputs.tfvars.json"
            generate_tfvars.main([str(path)])
            result = json.loads(path.read_text())
        self.assertEqual(result["default_capacity"], 2)
        self.assertEqual(result["apim_sku_name"], "StandardV2")
        self.assertFalse(result["zone_redundant"])
        self.assertFalse(result["enable_claude_desktop_delegated_auth"])
        self.assertNotIn("claude_desktop_client_id", result)
        self.assertNotIn("claude_desktop_delegated_scope", result)
        self.assertEqual(result["foundry_resource_id"], "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/foundry-rg/providers/Microsoft.CognitiveServices/accounts/foundry")
        self.assertEqual(result["secondary_foundry_base_url"], "")
        self.assertEqual(result["secondary_foundry_resource_id"], "")

    def test_derives_secondary_foundry_resource_id(self):
        inputs = dict(ENV,
            SECONDARY_FOUNDRY_BASE_URL="https://secondary.services.ai.azure.com/anthropic",
            SECONDARY_FOUNDRY_SUBSCRIPTION_ID="33333333-3333-3333-3333-333333333333",
            SECONDARY_FOUNDRY_RESOURCE_GROUP="secondary-foundry-rg",
            SECONDARY_FOUNDRY_ACCOUNT_NAME="secondary-foundry",
        )
        with patch.dict(os.environ, inputs, clear=True):
            result = generate_tfvars.values()
        self.assertEqual(result["secondary_foundry_base_url"], "https://secondary.services.ai.azure.com/anthropic")
        self.assertEqual(result["secondary_foundry_resource_id"], "/subscriptions/33333333-3333-3333-3333-333333333333/resourceGroups/secondary-foundry-rg/providers/Microsoft.CognitiveServices/accounts/secondary-foundry")

    def test_secondary_foundry_identity_requires_base_url(self):
        inputs = dict(ENV, SECONDARY_FOUNDRY_BASE_URL="https://secondary.services.ai.azure.com/anthropic")
        with patch.dict(os.environ, inputs, clear=True):
            with self.assertRaisesRegex(ValueError, "SECONDARY_FOUNDRY_SUBSCRIPTION_ID must be set"):
                generate_tfvars.values()

    def test_uses_apim_runtime_inputs(self):
        inputs = dict(ENV, APIM_SKU="PremiumV2", APIM_ZONE_REDUNDANT="true")
        with patch.dict(os.environ, inputs, clear=True):
            result = generate_tfvars.values()
        self.assertEqual(result["apim_sku_name"], "PremiumV2")
        self.assertTrue(result["zone_redundant"])

    def test_desktop_inputs_are_required_only_when_enabled(self):
        inputs = dict(ENV, CLAUDE_DESKTOP_DELEGATED_AUTH_ENABLED="true")
        with patch.dict(os.environ, inputs, clear=True):
            with self.assertRaisesRegex(ValueError, "CLAUDE_DESKTOP_CLIENT_ID must be set"):
                generate_tfvars.values()

    def test_rejects_invalid_boolean(self):
        invalid = dict(ENV, DEPLOY_SECONDARY="yes")
        with patch.dict(os.environ, invalid, clear=True):
            with self.assertRaisesRegex(ValueError, "DEPLOY_SECONDARY must be true or false"):
                generate_tfvars.values()


if __name__ == "__main__":
    unittest.main()
