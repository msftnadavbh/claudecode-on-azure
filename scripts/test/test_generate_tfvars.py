#!/usr/bin/env python3
import copy
import base64
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


def write_policy_module(directory):
    """Provider-free evaluation of real locals/templates, with only resource outputs stubbed."""
    (directory / "variables.tf").write_text((ROOT / "infra/tofu/variables.tf").read_text())
    main = (ROOT / "infra/tofu/main.tf").read_text()
    bindings = "\n".join(line for line in main.splitlines() if re.match(
        r"  (greenfield|effective_foundry_base_url|effective_foundry_resource_id|secondary_foundry_base_url|secondary_foundry_resource_id)\s*=", line))
    bindings = bindings.replace("azapi_resource.greenfield_foundry[0]", "local.test_foundry")
    locals_source = main[main.index("  apim_instances = merge({"):main.index("  operations = {")]
    template = re.search(r'xml_content\s*=\s*(templatefile\(.*?\n  \}\))', main, re.S).group(1)
    template = template.replace("${path.module}", str(ROOT / "infra/tofu"))
    template = template.replace("each.value.foundry_resource_id", "instance.foundry_resource_id")
    (directory / "main.tf").write_text('''locals {
  test_foundry = {
    name = var.foundry_account_name
    id = "/subscriptions/${var.foundry_subscription_id}/resourceGroups/${var.resource_group_name}/providers/Microsoft.CognitiveServices/accounts/${var.foundry_account_name}"
  }
''' + bindings + "\n" + locals_source + "\n  rendered_policies = { for key, instance in local.apim_instances : key => " + template + " }\n}\n")


def evaluate_policy_module(directory, inputs):
    path = directory / "inputs.tfvars.json"
    path.write_text(json.dumps(inputs))
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(directory), "TMPDIR": str(directory),
           "CHECKPOINT_DISABLE": "1", "TF_IN_AUTOMATION": "1"}
    return subprocess.run(["tofu", "console", "-no-color", f"-var-file={path}"], cwd=directory, env=env,
                          input="jsonencode(local.rendered_policies)\n", capture_output=True, text=True, timeout=30)


def inventory_configuration(policy):
    node = ET.fromstring(policy).find(".//set-variable[@name='inventoryConfiguration']")
    return json.loads(base64.b64decode(node.get("value")))


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
    """Evaluate the real variable rules and per-instance template without backend/providers."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        write_policy_module(self.directory)
        with patch.dict(os.environ, CATALOG_ENV, clear=True):
            self.inputs = generate_tfvars.values()

    def evaluate(self, inputs):
        return evaluate_policy_module(self.directory, inputs)

    def result(self, inputs):
        result = self.evaluate(inputs)
        self.assertEqual(result.returncode, 0, result.stderr)
        # console can exit zero after variable validation errors; stderr must also be empty.
        self.assertEqual(result.stderr, "")
        return json.loads(json.loads(result.stdout))

    def test_reviewed_catalog_does_not_drive_runtime_inventory(self):
        result = self.result(dict(self.inputs, model_catalog=CATALOG))
        self.assertEqual(result, self.result(self.inputs))
        config = inventory_configuration(result["primary"])
        self.assertEqual(config, {"account_resource_id": self.inputs["foundry_resource_id"],
                                  "pins": {role: self.inputs[f"{role}_deployment_name"] for role in ("opus", "sonnet", "haiku")}})
        root = ET.fromstring(result["primary"])
        self.assertIsNone(root.find("inbound/set-variable[@name='modelCatalog']"))
        self.assertIsNone(root.find("inbound/set-variable[@name='requestedModel']"))
        models_when = next(node for node in root.findall("inbound/choose/when")
                           if node.get("condition") == '@(context.Operation.Id == "models" && context.Request.Method == "GET")')
        self.assertEqual(len(models_when.findall(".//send-request")), 1)
        loop = models_when.find("choose/when/retry")
        page = ET.parse(ROOT / "apim/policies/claude-models-page.xml").getroot()
        self.assertEqual(loop.attrib, {"condition": page.find("when").get("condition"),
                                       "count": "2", "interval": "1", "first-fast-retry": "true"})
        self.assertEqual([node.tag for node in loop], ["choose"])
        self.assertEqual(len(models_when.findall(".//cache-lookup-value")), 1)
        self.assertEqual(len(models_when.findall(".//cache-store-value")), 1)
        for forbidden in ("${", "{{not-a-named-value}}", "FutureHostingSKU", "claude-orbit-fast"):
            self.assertNotIn(forbidden, result["primary"])
        main = (ROOT / "infra/tofu/main.tf").read_text()
        for dead in ("gateway_model_ids", "gateway_model_metadata", "public_model_catalog", "model_catalog_base64"):
            self.assertNotIn(dead, main)

    def test_primary_secondary_and_greenfield_bind_the_actual_instance(self):
        secondary = self.inputs["foundry_resource_id"].replace("/accounts/foundry", "/accounts/secondary")
        result = self.result(dict(self.inputs, deploy_secondary=True, secondary_foundry_resource_id=secondary))
        self.assertEqual(inventory_configuration(result["primary"])["account_resource_id"], self.inputs["foundry_resource_id"])
        self.assertEqual(inventory_configuration(result["secondary"])["account_resource_id"], secondary)
        shared = self.result(dict(self.inputs, deploy_secondary=True))
        self.assertEqual(shared["primary"], shared["secondary"])
        greenfield = dict(self.inputs, deployment_mode="greenfield", claude_model_deployment_name="claude-one",
                          foundry_account_name="greenfield", foundry_subscription_id="33333333-3333-3333-3333-333333333333")
        config = inventory_configuration(self.result(greenfield)["primary"])
        self.assertEqual(config["pins"], dict.fromkeys(("opus", "sonnet", "haiku"), "claude-one"))
        self.assertEqual(config["account_resource_id"], "/subscriptions/33333333-3333-3333-3333-333333333333/resourceGroups/gateway-rg/providers/Microsoft.CognitiveServices/accounts/greenfield")

    def test_configuration_is_data_not_csharp_xml_or_named_value_injection(self):
        malicious = 'claude-\"<&{{not-a-named-value}}${not_a_template}\\\n'
        rejected = self.evaluate(dict(self.inputs, opus_deployment_name=malicious))
        self.assertIn("Error:", rejected.stderr)
        self.assertIn("opus_deployment_name", rejected.stderr)
        result = self.result(dict(self.inputs, model_catalog=CATALOG))
        pins = {role: self.inputs[f"{role}_deployment_name"] for role in ("opus", "sonnet", "haiku")}
        self.assertEqual(inventory_configuration(result["primary"])["pins"], pins)
        for pin in pins.values():
            self.assertNotIn(pin, result["primary"])
        self.assertNotIn(malicious, result["primary"])
        self.assertNotIn("{{not-a-named-value}}", result["primary"])
        self.assertNotIn("${not_a_template}", result["primary"])

    def test_all_four_deployment_pins_reject_invalid_syntax_before_policy_use(self):
        for variable in ("opus_deployment_name", "sonnet_deployment_name", "haiku_deployment_name", "claude_model_deployment_name"):
            inputs = dict(self.inputs)
            if variable == "claude_model_deployment_name":
                inputs.update(deployment_mode="greenfield", foundry_account_name="greenfield")
            for bad in ("claude/bad", "claude bad", 'claude-"bad', "claude\n", "_claude", "-claude", ".claude", "claude-é"):
                with self.subTest(variable=variable, value=bad):
                    result = self.evaluate(dict(inputs, **{variable: bad}))
                    self.assertIn("Error:", result.stderr)
                    self.assertIn(variable, result.stderr)

    def test_valid_pins_and_inactive_mode_empty_values_are_preserved(self):
        roles = ("opus", "sonnet", "haiku")
        for valid in ("A", "1Deployment_A.v2-prod", "claude-" + "x" * 80):
            with self.subTest(value=valid):
                existing = dict(self.inputs, claude_model_deployment_name="",
                                **{f"{role}_deployment_name": valid for role in roles})
                config = inventory_configuration(self.result(existing)["primary"])
                self.assertEqual(config["pins"], dict.fromkeys(roles, valid))
                greenfield = dict(self.inputs, deployment_mode="greenfield", foundry_account_name="greenfield",
                                  claude_model_deployment_name=valid, **{f"{role}_deployment_name": "" for role in roles})
                config = inventory_configuration(self.result(greenfield)["primary"])
                self.assertEqual(config["pins"], dict.fromkeys(roles, valid))

    def test_both_account_ids_reject_url_injection_and_preserve_valid_resource_names(self):
        account = self.inputs["foundry_resource_id"]
        for variable in ("foundry_resource_id", "secondary_foundry_resource_id"):
            for bad in (account + "?x=y", account + "#fragment", account + "/../other", account + "%2fother",
                        account + "\\other", account + "\n", account.replace("/foundry-rg/", "/../"),
                        account.replace("/foundry-rg/", "/a%252fb/"), account.replace("/foundry-rg/", "/a b/"),
                        account.replace("22222222-2222-2222-2222-222222222222", "-" * 36)):
                with self.subTest(variable=variable, value=bad):
                    result = self.evaluate(dict(self.inputs, **{variable: bad}))
                    self.assertIn("Error:", result.stderr)
                    self.assertIn(variable, result.stderr)
            valid = account.replace("/foundry-rg/", "/Grüppe_(東).test/").replace("/accounts/foundry", "/accounts/Legacy_Account.v1")
            self.result(dict(self.inputs, **{variable: valid}))

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
