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
        self.assertTrue(result["zone_redundant"])
        self.assertEqual(result["foundry_resource_id"], "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/foundry-rg/providers/Microsoft.CognitiveServices/accounts/foundry")

    def test_rejects_invalid_boolean(self):
        invalid = dict(ENV, DEPLOY_SECONDARY="yes")
        with patch.dict(os.environ, invalid, clear=True):
            with self.assertRaisesRegex(ValueError, "DEPLOY_SECONDARY must be true or false"):
                generate_tfvars.values()


if __name__ == "__main__":
    unittest.main()
