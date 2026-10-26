#!/usr/bin/env python3
import base64
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tofu"))
import generate_tfvars

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((Path(__file__).parent / "fixtures/model-discovery/catalog.json").read_text())

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
CATALOG_ENV = dict(ENV, **{f"ANTHROPIC_DEFAULT_{role}_MODEL": f"claude-{role.lower()}-pinned" for role in ("OPUS", "SONNET", "HAIKU")})


class GenerateTfvarsTests(unittest.TestCase):
    def test_monthly_quota(self):
        for raw, expected in [(None, 0), ("", 0), ("  ", 0), ("0", 0), ("123", 123), ("9223372036854775807", 9223372036854775807)]:
            inputs = ENV if raw is None else dict(ENV, PER_USER_MONTHLY_TOKEN_QUOTA=raw)
            with self.subTest(raw=raw), patch.dict(os.environ, inputs, clear=True):
                self.assertEqual(generate_tfvars.values()["per_user_monthly_token_quota"], expected)
        for raw in ("-1", "1.5", "1e3", "null", "9223372036854775808", "+1", "١"):
            with self.subTest(raw=raw), patch.dict(os.environ, dict(ENV, PER_USER_MONTHLY_TOKEN_QUOTA=raw), clear=True):
                with self.assertRaisesRegex(ValueError, "PER_USER_MONTHLY_TOKEN_QUOTA"):
                    generate_tfvars.values()

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
        self.assertEqual(result["deployment_mode"], "existing")
        self.assertNotIn("model_catalog", result)

    def test_catalog_embeds_validated_contents_and_freezes_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.json"
            catalog_path.write_text(json.dumps(CATALOG))
            output = Path(directory) / "inputs.tfvars.json"
            with patch.dict(os.environ, dict(CATALOG_ENV, MODEL_CATALOG_FILE=str(catalog_path)), clear=True):
                generate_tfvars.main([str(output)])
                frozen = output.read_bytes()
                self.assertEqual(json.loads(frozen)["model_catalog"], CATALOG)
                self.assertNotIn(str(catalog_path), frozen.decode())
                changed = copy.deepcopy(CATALOG)
                changed["models"][2]["description"] = "New review required"
                catalog_path.write_text(json.dumps(changed))
                self.assertEqual(output.read_bytes(), frozen)
                generate_tfvars.main([str(output)])
                self.assertNotEqual(sha256(output.read_bytes()).hexdigest(), sha256(frozen).hexdigest())

    def test_catalog_errors_leave_existing_tfvars_unmodified(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inputs.tfvars.json"
            output.write_bytes(b"reviewed inputs\n")
            catalog_path = Path(directory) / "catalog.json"
            mutations = [
                lambda c: c.update(schema_version=2),
                lambda c: c.update(account_resource_id=c["account_resource_id"] + "-wrong"),
                lambda c: c.update(base_url="https://wrong.services.ai.azure.com/anthropic"),
                lambda c: c["models"].pop(),
                lambda c: c["models"].append(copy.deepcopy(c["models"][0])),
                lambda c: c.update(default_model="claude-orbit-fast"),
                lambda c: c.update(models=[]),
            ]
            for index, mutate in enumerate(mutations):
                with self.subTest(mutation=index):
                    catalog = copy.deepcopy(CATALOG)
                    mutate(catalog)
                    catalog_path.write_text(json.dumps(catalog))
                    with patch.dict(os.environ, dict(CATALOG_ENV, MODEL_CATALOG_FILE=str(catalog_path)), clear=True):
                        with self.assertRaises(ValueError):
                            generate_tfvars.main([str(output)])
                    self.assertEqual(output.read_bytes(), b"reviewed inputs\n")
            catalog_path.unlink()
            with patch.dict(os.environ, dict(CATALOG_ENV, MODEL_CATALOG_FILE=str(catalog_path)), clear=True):
                with self.assertRaisesRegex(ValueError, "cannot read model catalog"):
                    generate_tfvars.main([str(output)])
            self.assertEqual(output.read_bytes(), b"reviewed inputs\n")

    def test_any_validation_failure_happens_before_opening_output(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, dict(ENV, PER_USER_RATE_LIMIT="invalid"), clear=True):
            output = Path(directory) / "inputs.tfvars.json"
            output.write_bytes(b"reviewed inputs\n")
            with self.assertRaises(ValueError):
                generate_tfvars.main([str(output)])
            self.assertEqual(output.read_bytes(), b"reviewed inputs\n")

    def test_catalog_rejects_greenfield_and_distinct_secondary_but_allows_shared_account(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.json"
            catalog_path.write_text(json.dumps(CATALOG))
            base = dict(CATALOG_ENV, MODEL_CATALOG_FILE=str(catalog_path))
            for change in ({"DEPLOYMENT_MODE": "greenfield"},
                           {"SECONDARY_FOUNDRY_SUBSCRIPTION_ID": "33333333-3333-3333-3333-333333333333"},
                           {"SECONDARY_FOUNDRY_ACCOUNT_NAME": "different"},
                           {"SECONDARY_FOUNDRY_RESOURCE_GROUP": "different"},
                           {"SECONDARY_FOUNDRY_BASE_URL": "https://other.services.ai.azure.com/anthropic",
                            "SECONDARY_FOUNDRY_SUBSCRIPTION_ID": ENV["FOUNDRY_SUBSCRIPTION_ID"],
                            "SECONDARY_FOUNDRY_RESOURCE_GROUP": ENV["FOUNDRY_RESOURCE_GROUP"],
                            "SECONDARY_FOUNDRY_ACCOUNT_NAME": ENV["FOUNDRY_ACCOUNT_NAME"]}):
                with self.subTest(change=change), patch.dict(os.environ, dict(base, **change), clear=True):
                    with self.assertRaisesRegex(ValueError, "MODEL_CATALOG_FILE"):
                        generate_tfvars.values()
            shared = dict(base, DEPLOY_SECONDARY="true", APIM_SECONDARY_NAME="secondary-apim", AZURE_SECONDARY_LOCATION="westus",
                          **{f"SECONDARY_{key}": ENV[key] for key in ("FOUNDRY_SUBSCRIPTION_ID", "FOUNDRY_RESOURCE_GROUP", "FOUNDRY_ACCOUNT_NAME", "FOUNDRY_BASE_URL")})
            with patch.dict(os.environ, shared, clear=True):
                self.assertEqual(generate_tfvars.values()["model_catalog"], CATALOG)
            for name in ("FOUNDRY_BASE_URL", "SECONDARY_FOUNDRY_BASE_URL"):
                with self.subTest(url=name), patch.dict(os.environ, dict(shared, **{name: ENV["FOUNDRY_BASE_URL"].replace("/anthropic", "/ANTHROPIC")}), clear=True):
                    with self.assertRaises(ValueError):
                        generate_tfvars.values()

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

    def test_writes_greenfield_values(self):
        inputs = dict(ENV, DEPLOYMENT_MODE="greenfield", ARM_SUBSCRIPTION_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            ACCEPT_ANTHROPIC_MARKETPLACE_TERMS="true", FOUNDRY_PROJECT_NAME="project", FOUNDRY_LOCATION="eastus",
            CLAUDE_MODEL_DEPLOYMENT_NAME="claude", CLAUDE_MODEL_NAME="claude-sonnet", CLAUDE_MODEL_VERSION="1",
            CLAUDE_MODEL_SKU="GlobalStandard", CLAUDE_MODEL_CAPACITY="5", CLAUDE_ORGANIZATION_NAME="Contoso",
            CLAUDE_COUNTRY_CODE="US", CLAUDE_INDUSTRY="technology")
        for name in ("FOUNDRY_BASE_URL", "FOUNDRY_SUBSCRIPTION_ID", "FOUNDRY_RESOURCE_GROUP", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
            inputs.pop(name)
        with patch.dict(os.environ, inputs, clear=True):
            result = generate_tfvars.values()
        self.assertEqual(result["foundry_base_url"], "https://foundry.services.ai.azure.com/anthropic")
        self.assertEqual(result["foundry_subscription_id"], "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.assertEqual(result["opus_deployment_name"], "")
        self.assertEqual(result["claude_model_capacity"], 5)

    def test_greenfield_requires_marketplace_acceptance(self):
        inputs = dict(ENV, DEPLOYMENT_MODE="greenfield", ARM_SUBSCRIPTION_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        with patch.dict(os.environ, inputs, clear=True):
            with self.assertRaisesRegex(ValueError, "MARKETPLACE"):
                generate_tfvars.values()

    def test_greenfield_rejects_secondary_foundry(self):
        inputs = dict(ENV, DEPLOYMENT_MODE="greenfield", ARM_SUBSCRIPTION_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                      SECONDARY_FOUNDRY_BASE_URL="https://secondary.services.ai.azure.com/anthropic")
        with patch.dict(os.environ, inputs, clear=True):
            with self.assertRaisesRegex(ValueError, "secondary Foundry"):
                generate_tfvars.values()

    def test_greenfield_validates_attestation_and_capacity(self):
        inputs = dict(ENV, DEPLOYMENT_MODE="greenfield", ARM_SUBSCRIPTION_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                      ACCEPT_ANTHROPIC_MARKETPLACE_TERMS="true", FOUNDRY_PROJECT_NAME="project", FOUNDRY_LOCATION="eastus",
                      CLAUDE_MODEL_DEPLOYMENT_NAME="claude", CLAUDE_MODEL_NAME="claude-sonnet", CLAUDE_MODEL_VERSION="1",
                      CLAUDE_MODEL_SKU="S0", CLAUDE_MODEL_CAPACITY="0", CLAUDE_ORGANIZATION_NAME=" example ",
                      CLAUDE_COUNTRY_CODE="us", CLAUDE_INDUSTRY="unknown")
        for name in ("FOUNDRY_BASE_URL", "FOUNDRY_SUBSCRIPTION_ID", "FOUNDRY_RESOURCE_GROUP", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
            inputs.pop(name)
        with patch.dict(os.environ, inputs, clear=True):
            with self.assertRaisesRegex(ValueError, "CLAUDE_MODEL_SKU"):
                generate_tfvars.values()

    def test_greenfield_requires_trimmed_organization(self):
        inputs = dict(ENV, DEPLOYMENT_MODE="greenfield", ARM_SUBSCRIPTION_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                      ACCEPT_ANTHROPIC_MARKETPLACE_TERMS="true", FOUNDRY_PROJECT_NAME="project", FOUNDRY_LOCATION="eastus",
                      CLAUDE_MODEL_DEPLOYMENT_NAME="claude", CLAUDE_MODEL_NAME="claude-sonnet", CLAUDE_MODEL_VERSION="1",
                      CLAUDE_MODEL_SKU="GlobalStandard", CLAUDE_MODEL_CAPACITY="5", CLAUDE_ORGANIZATION_NAME=" Contoso",
                      CLAUDE_COUNTRY_CODE="US", CLAUDE_INDUSTRY="technology")
        for name in ("FOUNDRY_BASE_URL", "FOUNDRY_SUBSCRIPTION_ID", "FOUNDRY_RESOURCE_GROUP", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
            inputs.pop(name)
        with patch.dict(os.environ, inputs, clear=True):
            with self.assertRaisesRegex(ValueError, "CLAUDE_ORGANIZATION_NAME must be trimmed"):
                generate_tfvars.values()

    def test_greenfield_validates_country_industry_and_capacity(self):
        base = dict(ENV, DEPLOYMENT_MODE="greenfield", ARM_SUBSCRIPTION_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    ACCEPT_ANTHROPIC_MARKETPLACE_TERMS="true", FOUNDRY_PROJECT_NAME="project", FOUNDRY_LOCATION="eastus",
                    CLAUDE_MODEL_DEPLOYMENT_NAME="claude", CLAUDE_MODEL_NAME="claude-sonnet", CLAUDE_MODEL_VERSION="1",
                    CLAUDE_MODEL_SKU="GlobalStandard", CLAUDE_MODEL_CAPACITY="5", CLAUDE_ORGANIZATION_NAME="Contoso",
                    CLAUDE_COUNTRY_CODE="US", CLAUDE_INDUSTRY="technology")
        for name in ("FOUNDRY_BASE_URL", "FOUNDRY_SUBSCRIPTION_ID", "FOUNDRY_RESOURCE_GROUP", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
            base.pop(name)
        for name, value in (("CLAUDE_MODEL_CAPACITY", "0"), ("CLAUDE_COUNTRY_CODE", "us"), ("CLAUDE_INDUSTRY", "unknown")):
            with self.subTest(name=name), patch.dict(os.environ, dict(base, **{name: value}), clear=True):
                with self.assertRaises(ValueError):
                    generate_tfvars.values()


@unittest.skipUnless(shutil.which("tofu"), "OpenTofu is required for offline HCL evaluation")
class ModelCatalogTofuTests(unittest.TestCase):
    """Evaluate the real variable rules/projection/template without any backend or providers."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        (self.directory / "variables.tf").write_text((ROOT / "infra/tofu/variables.tf").read_text())
        main = (ROOT / "infra/tofu/main.tf").read_text()
        locals_source = main[main.index("  named_values = {"):main.index("  operations = {")]
        template = re.search(r'xml_content\s*=\s*(templatefile\(.*?\n  \}\))', main, re.S).group(1)
        template = template.replace("${path.module}", str(ROOT / "infra/tofu"))
        (self.directory / "main.tf").write_text('locals {\n  greenfield = var.deployment_mode == "greenfield"\n' + locals_source + "\n  rendered_policy = " + template + "\n}\n")
        with patch.dict(os.environ, CATALOG_ENV, clear=True):
            self.inputs = generate_tfvars.values()

    def evaluate(self, inputs):
        path = self.directory / "inputs.tfvars.json"
        path.write_text(json.dumps(inputs))
        return subprocess.run(["tofu", "console", "-no-color", f"-var-file={path}"], cwd=self.directory,
                              input="jsonencode({public=local.public_model_catalog, policy=local.rendered_policy})\n",
                              capture_output=True, text=True, timeout=30)

    def result(self, inputs):
        result = self.evaluate(inputs)
        self.assertEqual(result.returncode, 0, result.stderr)
        # console can exit zero after variable validation errors; stderr must also be empty.
        self.assertEqual(result.stderr, "")
        return json.loads(json.loads(result.stdout))

    def test_rendered_catalog_is_one_safe_public_projection(self):
        result = self.result(dict(self.inputs, model_catalog=CATALOG))
        models = {model["id"]: model for model in CATALOG["models"]}
        expected_ids = ["claude-opus-pinned", "claude-sonnet-pinned", "claude-haiku-pinned", "claude-orbit-fast"]
        expected = {"data": [{key: models[identifier][key] for key in ("id", "display_name", "description")} for identifier in expected_ids]}
        self.assertEqual(result["public"], expected)
        root = ET.fromstring(result["policy"])
        value = root.find("inbound/set-variable[@name='modelCatalog']").get("value")
        payload = re.search(r'FromBase64String\("([A-Za-z0-9+/=]+)"\)', value).group(1)
        self.assertEqual(json.loads(base64.b64decode(payload, validate=True)), expected)
        self.assertNotIn("${model_catalog_base64}", result["policy"])
        self.assertNotIn("{{not-a-named-value}}", result["policy"])
        self.assertNotIn("${not_a_template}", result["policy"])
        self.assertNotIn("FutureHostingSKU", result["policy"])
        self.assertEqual(result["policy"].count(payload), 1)
        returned = root.find(".//return-response/set-header[@name='Content-Type']/../set-body").text
        self.assertEqual(returned, '@((string)context.Variables["modelCatalog"])')
        membership = next(node.get("condition") for node in root.findall("inbound/choose/when") if 'JObject.Parse' in node.get("condition"))
        self.assertEqual(membership, '@(!JObject.Parse((string)context.Variables["modelCatalog"])["data"].Any(model => (string)model["id"] == (string)context.Variables["requestedModel"]))')

    def test_public_order_prioritizes_role_pins_over_older_models_and_deduplicates(self):
        catalog = copy.deepcopy(CATALOG)
        for role in ("sonnet", "haiku"):
            model = next(model for model in catalog["models"] if model["id"] == f"claude-{role}-pinned")
            catalog["models"].append({**model, "id": f"claude-{role}-aaa-older"})
        catalog["models"][1:] = sorted(catalog["models"][1:], key=lambda model: model["id"])
        expected = ["claude-opus-pinned", "claude-sonnet-pinned", "claude-haiku-pinned",
                    "claude-haiku-aaa-older", "claude-orbit-fast", "claude-sonnet-aaa-older"]
        result = self.result(dict(self.inputs, model_catalog=catalog))
        self.assertEqual([model["id"] for model in result["public"]["data"]], expected)
        shared = dict(self.inputs, model_catalog=catalog,
                      **{f"{role}_deployment_name": "claude-opus-pinned" for role in ("opus", "sonnet", "haiku")})
        result = self.result(shared)
        self.assertEqual([model["id"] for model in result["public"]["data"]],
                         ["claude-opus-pinned", "claude-haiku-aaa-older", "claude-haiku-pinned",
                          "claude-orbit-fast", "claude-sonnet-aaa-older", "claude-sonnet-pinned"])

    def test_legacy_null_and_greenfield_projection_deduplicate_pins(self):
        for catalog in ({}, {"model_catalog": None}):
            result = self.result(dict(self.inputs, **catalog))
            self.assertEqual([row["id"] for row in result["public"]["data"]],
                             [self.inputs[f"{role}_deployment_name"] for role in ("opus", "sonnet", "haiku")])
        shared = dict(self.inputs, **{f"{role}_deployment_name": "shared" for role in ("opus", "sonnet", "haiku")})
        self.assertEqual([row["id"] for row in self.result(shared)["public"]["data"]], ["shared"])
        greenfield = dict(self.inputs, deployment_mode="greenfield", claude_model_deployment_name="claude-one")
        self.assertEqual([row["id"] for row in self.result(greenfield)["public"]["data"]], ["claude-one"])

    def test_direct_tfvars_reject_schema_duplicate_binding_default_and_role_errors(self):
        mutations = [
            lambda c: c.update(schema_version=2),
            lambda c: c.update(account_resource_id=c["account_resource_id"] + "-wrong"),
            lambda c: c.update(base_url="https://wrong.services.ai.azure.com/anthropic"),
            lambda c: c.update(default_model="claude-orbit-fast"),
            lambda c: c["models"].pop(),
            lambda c: c["models"].append(copy.deepcopy(c["models"][0])),
            lambda c: c["models"].append({**c["models"][0], "id": c["models"][0]["id"].upper()}),
            lambda c: c["models"][2].update(id="hidden-from-cli"),
            lambda c: c["models"][2].update(id=c["account_resource_id"]),
            lambda c: c.update(models=[]),
            lambda c: c["models"][0].update(description=""),
            lambda c: c["models"][0].update(model_version=""),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                catalog = copy.deepcopy(CATALOG)
                mutate(catalog)
                result = self.evaluate(dict(self.inputs, model_catalog=catalog))
                self.assertIn("Error:", result.stderr)
                self.assertIn("model_catalog", result.stderr)

    def test_direct_tfvars_catalog_rejects_greenfield_and_distinct_secondary(self):
        for change in ({"deployment_mode": "greenfield"},
                       {"foundry_base_url": CATALOG["base_url"].replace("/anthropic", "/ANTHROPIC")},
                       {"secondary_foundry_base_url": CATALOG["base_url"].replace("/anthropic", "/ANTHROPIC")},
                       {"secondary_foundry_base_url": "https://other.services.ai.azure.com/anthropic"},
                       {"secondary_foundry_resource_id": CATALOG["account_resource_id"] + "-other"}):
            with self.subTest(change=change):
                result = self.evaluate(dict(self.inputs, model_catalog=CATALOG, **change))
                self.assertIn("Error:", result.stderr)
                self.assertIn("model_catalog", result.stderr)
        self.result(dict(self.inputs, model_catalog=CATALOG, deploy_secondary=True,
                         secondary_foundry_base_url=self.inputs["foundry_base_url"],
                         secondary_foundry_resource_id=self.inputs["foundry_resource_id"]))

    def test_direct_tfvars_unknown_metadata_is_nullable(self):
        catalog = copy.deepcopy(CATALOG)
        catalog["models"][2].update(model_version=None, sku=None)
        self.result(dict(self.inputs, model_catalog=catalog))


if __name__ == "__main__":
    unittest.main()
