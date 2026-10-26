"""Synthetic/offline inventory tests: no Azure authentication or inference calls."""
from contextlib import redirect_stdout
import copy
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_catalog
import sync_claude_models as sync

FIXTURE = Path(__file__).parent / "fixtures/model-discovery/catalog.json"
CATALOG = json.loads(FIXTURE.read_text())
SUBSCRIPTION = "22222222-2222-2222-2222-222222222222"


def responses():
    account = {"id": CATALOG["account_resource_id"], "kind": "AIServices", "location": "eastus",
               "properties": {"provisioningState": "Succeeded", "customSubDomainName": "foundry"}}
    deployments, available = [], []
    for model in CATALOG["models"]:
        raw = {"name": model["model_name"], "version": model["model_version"], "format": "Anthropic"}
        deployments.append({"name": model["id"], "id": f"{account['id']}/deployments/{model['id']}",
                            "properties": {"provisioningState": "Succeeded", "model": raw,
                                           "versionUpgradeOption": "NoAutoUpgrade"},
                            "sku": {"name": model["sku"], "capacity": 5}})
        available.append({**raw, "capabilities": {"syntheticCapability": "false"},
                          "deprecation": {"inference": "2099-01-01"},
                          "skus": [{"name": model["sku"], "usageName": "synthetic-quota", "capacity": {"minimum": 1}}]})
    return [account, deployments, available,
            [{"name": {"value": "synthetic-quota"}, "currentValue": 5, "limit": 10, "unit": "Count"}]]


class SyncModelsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.catalog_path = self.directory / "catalog.json"
        self.report_path = self.directory / "report.json"
        self.args = ["--subscription", SUBSCRIPTION, "--resource-group", "foundry-rg", "--account", "foundry",
                     "--expected-base-url", CATALOG["base_url"], "--catalog-file", str(self.catalog_path),
                     "--report-file", str(self.report_path)]

    def seed(self, catalog=CATALOG):
        self.catalog_path.write_text(json.dumps(catalog, indent=2) + "\n")
        self.report_path.write_bytes(b"previous report\n")

    def invoke(self, replies=None, extra=(), expected=0):
        output = io.StringIO()
        with patch.object(sync, "az", side_effect=responses() if replies is None else replies) as command, redirect_stdout(output):
            self.assertEqual(sync.main(self.args + list(extra)), expected, output.getvalue())
        return json.loads(output.getvalue()), command

    def assert_preserved_failure(self, replies=None, extra=()):
        before = self.catalog_path.read_bytes(), self.report_path.read_bytes()
        result, command = self.invoke(replies, extra, expected=1)
        self.assertFalse(result["ok"])
        self.assertEqual((self.catalog_path.read_bytes(), self.report_path.read_bytes()), before)
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), ["catalog.json", "report.json"])
        return result, command

    def test_bootstrap_default_order_and_idempotence(self):
        result, _ = self.invoke(extra=("--default-model", CATALOG["default_model"]))
        first = self.catalog_path.read_bytes(), self.report_path.read_bytes()
        catalog = model_catalog.read_catalog(self.catalog_path)
        ids = [model["id"] for model in catalog["models"]]
        self.assertEqual(ids[0], CATALOG["default_model"])
        self.assertEqual(ids[1:], sorted(ids[1:]))
        self.assertEqual(result["catalog_sha256"], sha256(first[0]).hexdigest())
        shuffled = responses()
        shuffled[1].reverse()
        shuffled[2].reverse()
        self.invoke(shuffled)
        self.assertEqual((self.catalog_path.read_bytes(), self.report_path.read_bytes()), first)

    def test_adds_arbitrary_model_and_sku_preserving_default_and_labels(self):
        prior = copy.deepcopy(CATALOG)
        prior["models"] = [model for model in prior["models"] if model["id"] != "claude-orbit-fast"]
        self.seed(prior)
        self.invoke()
        catalog = model_catalog.read_catalog(self.catalog_path)
        self.assertEqual(catalog["default_model"], prior["default_model"])
        for model in prior["models"]:
            self.assertIn(model, catalog["models"])
        added = next(model for model in catalog["models"] if model["id"] == "claude-orbit-fast")
        self.assertEqual((added["model_name"], added["sku"]), ("claude-orbit-test", "FutureHostingSKU"))
        self.assertNotIn("capabilities", added)
        self.assertNotIn("supports1m", added)

    def test_publisher_identification_does_not_require_known_model_family(self):
        replies = responses()
        raw = replies[1][2]["properties"]["model"]
        raw.pop("format")
        raw.update(publisher="Anthropic", name="arbitrary-new-model")
        self.invoke(replies, extra=("--default-model", CATALOG["default_model"]))
        catalog = model_catalog.read_catalog(self.catalog_path)
        self.assertIn("arbitrary-new-model", [model["model_name"] for model in catalog["models"]])

    def test_failed_and_non_anthropic_excluded_catalog_candidates_not_deployed(self):
        replies = responses()
        failed = copy.deepcopy(replies[1][0])
        failed.pop("id")
        failed["name"] = "failed-deployment"
        failed["properties"]["provisioningState"] = "Failed"
        other = {"name": "other-deployment", "properties": {"provisioningState": "Succeeded",
                 "model": {"name": "other", "format": "OpenAI"}}}
        replies[1].extend([failed, other])
        replies[2].extend([
            {"name": "other", "format": "OpenAI", "version": "1", "skus": []},
            {"name": "claude-orbit-test", "format": "Anthropic", "version": "test-3", "skus": [{"name": "FutureHostingSKU"}]},
        ])
        replies[2][2]["skus"].append({"name": "DifferentSKU"})
        self.invoke(replies, extra=("--default-model", CATALOG["default_model"]))
        catalog = model_catalog.read_catalog(self.catalog_path)
        self.assertEqual({model["id"] for model in catalog["models"]}, {model["id"] for model in CATALOG["models"]})
        report = json.loads(self.report_path.read_text())
        self.assertEqual({row["id"] for row in report["excluded_deployments"]}, {"failed-deployment", "other-deployment"})
        self.assertEqual({(row["model_name"], row["model_version"], row["sku"]) for row in report["catalog_only_candidates"]},
                         {("claude-orbit-test", "test-2", "DifferentSKU"), ("claude-orbit-test", "test-3", "FutureHostingSKU")})
        self.assertEqual(report["deployed"][0]["version_upgrade_option"], "NoAutoUpgrade")
        self.assertEqual(report["deployed"][0]["capacity"], 5)
        self.assertEqual(report["catalog"][0]["metadata"]["deprecation"], {"inference": "2099-01-01"})
        self.assertEqual(report["catalog"][0]["metadata"]["capabilities"], {"syntheticCapability": "false"})
        self.assertEqual(report["quota"][0]["limit"], 10)

    def test_missing_or_unsuccessful_deployments_retained_and_reported_stale(self):
        self.seed()
        replies = responses()
        replies[1] = [row for row in replies[1] if row["name"] != "claude-haiku-pinned"]
        replies[1][-1]["properties"]["provisioningState"] = "Updating"
        self.invoke(replies)
        self.assertEqual(model_catalog.read_catalog(self.catalog_path), CATALOG)
        stale = json.loads(self.report_path.read_text())["stale"]
        self.assertEqual(stale, [{"id": "claude-haiku-pinned", "reason": "missing from deployment inventory"},
                                 {"id": "claude-sonnet-pinned", "reason": "provisioning state Updating"}])

    def test_all_failed_but_nonempty_inventory_retains_last_known_catalog(self):
        self.seed()
        replies = responses()
        for row in replies[1]:
            row["properties"] = {"provisioningState": "Failed"}
        self.invoke(replies)
        self.assertEqual(model_catalog.read_catalog(self.catalog_path), CATALOG)
        self.assertEqual(len(json.loads(self.report_path.read_text())["stale"]), len(CATALOG["models"]))

    def test_unknown_version_sku_are_null_not_catalog_guesses(self):
        replies = responses()
        replies[1][2]["properties"]["model"]["version"] = " "
        replies[1][2].pop("sku")
        replies[3] = []
        self.invoke(replies, extra=("--default-model", CATALOG["default_model"]))
        added = next(model for model in model_catalog.read_catalog(self.catalog_path)["models"] if model["id"] == "claude-orbit-fast")
        self.assertIsNone(added["model_version"])
        self.assertIsNone(added["sku"])
        warnings = json.loads(self.report_path.read_text())["warnings"]
        self.assertTrue(any("model version is unknown" in warning for warning in warnings))
        self.assertTrue(any("SKU is unknown" in warning for warning in warnings))
        self.assertTrue(any("No Claude/Anthropic quota" in warning for warning in warnings))

    def test_existing_id_retargeting_fails_without_touching_outputs(self):
        for field, value in (("name", "claude-different"), ("version", "test-new"),
                             ("source", "/synthetic/new-source"), ("sourceAccount", "/synthetic/new-account"),
                             ("sku", "DifferentHostingSKU"), ("format", "OpenAI")):
            with self.subTest(field=field):
                self.seed()
                replies = responses()
                if field == "sku":
                    replies[1][0]["sku"]["name"] = value
                else:
                    replies[1][0]["properties"]["model"][field] = value
                result, _ = self.assert_preserved_failure(replies)
                self.assertIn("review required", result["errors"][0])

    def test_invalid_partial_empty_or_duplicate_inventory_preserves_bytes(self):
        mutations = [
            lambda r: r[0].update(kind="OpenAI"),
            lambda r: r[0].update(id=CATALOG["account_resource_id"] + "-wrong"),
            lambda r: r[0]["properties"].update(customSubDomainName="wrong"),
            lambda r: r[0]["properties"].update(provisioningState="Updating"),
            lambda r: r.__setitem__(1, []),
            lambda r: r.__setitem__(1, {"value": r[1], "nextLink": "https://untrusted.invalid"}),
            lambda r: r[1].append(None),
            lambda r: r[1].append(copy.deepcopy(r[1][0])),
            lambda r: r[1].append({**copy.deepcopy(r[1][0]), "name": r[1][0]["name"].upper()}),
            lambda r: r[1][0].update(id="/wrong/account/deployments/claude-opus-pinned"),
            lambda r: r[1][0]["properties"].pop("model"),
            lambda r: r[1][0]["properties"]["model"].pop("name"),
            lambda r: r[1][0]["properties"].pop("provisioningState"),
            lambda r: r[1][0].update(provisioningState="Failed"),
            lambda r: r[1][0].update(sku=[]),
            lambda r: r[1][0]["properties"].update(model=[]),
            lambda r: r[1][0]["properties"]["model"].update(format=42),
            lambda r: r.__setitem__(2, []),
            lambda r: r.__setitem__(2, {"value": r[2]}),
            lambda r: r[2].append(copy.deepcopy(r[2][0])),
            lambda r: r[2][0].update(skus={"name": "Partial"}),
            lambda r: r[2].append({"format": "OpenAI"}),
            lambda r: r[1].append({"name": "other", "properties": {"provisioningState": "Succeeded", "model": {"format": "OpenAI"}}}),
            lambda r: r.__setitem__(3, {"value": r[3]}),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                self.seed()
                replies = responses()
                mutate(replies)
                self.assert_preserved_failure(replies)

    def test_undiscoverable_deployment_name_is_reported_not_aliased(self):
        self.seed()
        replies = responses()
        replies[1][2].pop("id")
        replies[1][2]["name"] = "unroutable-picker-name"
        result, _ = self.assert_preserved_failure(replies)
        self.assertIn("must contain claude or anthropic", result["errors"][0])

    def test_catalog_schema_and_binding_errors_stop_before_azure(self):
        mutations = [
            lambda c: c.update(schema_version=True),
            lambda c: c.update(schema_version=2),
            lambda c: c.update(account_resource_id=c["account_resource_id"] + "-wrong"),
            lambda c: c.update(base_url="https://wrong.services.ai.azure.com/anthropic"),
            lambda c: c.update(models=[]),
            lambda c: c["models"].append(copy.deepcopy(c["models"][0])),
            lambda c: c["models"].append({**c["models"][0], "id": c["models"][0]["id"].upper()}),
            lambda c: c["models"][0].update(sku=""),
            lambda c: c["models"][0].update(model_version=123),
            lambda c: c["models"][0].update(capabilities={}),
            lambda c: c["models"][0].update(id=c["account_resource_id"]),
            lambda c: c["models"][0].pop("description"),
            lambda c: c["models"][0].update(hosting={}),
            lambda c: c.update(default_model="claude-not-deployed"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                catalog = copy.deepcopy(CATALOG)
                mutate(catalog)
                self.seed(catalog)
                _, command = self.assert_preserved_failure()
                command.assert_not_called()
        for raw in (b"{", b'{"schema_version":1,"schema_version":1}', b'{"n":NaN}'):
            self.seed()
            self.catalog_path.write_bytes(raw)
            _, command = self.assert_preserved_failure()
            command.assert_not_called()

    def test_default_is_explicit_at_bootstrap_and_cannot_be_changed(self):
        _, command = self.invoke(expected=1)
        command.assert_not_called()
        self.assertFalse(self.catalog_path.exists())
        self.assertFalse(self.report_path.exists())
        self.seed()
        _, command = self.assert_preserved_failure(extra=("--default-model", "claude-orbit-fast"))
        command.assert_not_called()

    def test_bootstrap_requires_a_deployed_default(self):
        self.invoke(extra=("--default-model", "claude-not-deployed"), expected=1)
        self.assertFalse(self.catalog_path.exists())
        self.assertFalse(self.report_path.exists())

    def test_read_only_fixed_azure_commands_are_bounded_and_explicit(self):
        self.seed()
        replies = iter(responses())
        output = io.StringIO()
        with patch.object(sync.subprocess, "run", side_effect=lambda *a, **kw: SimpleNamespace(stdout=json.dumps(next(replies)))) as command, redirect_stdout(output):
            self.assertEqual(sync.main(self.args), 0)
        self.assertEqual(command.call_count, 4)
        prefixes = [("az", "cognitiveservices", "account", "show"),
                    ("az", "cognitiveservices", "account", "deployment", "list"),
                    ("az", "cognitiveservices", "account", "list-models"),
                    ("az", "cognitiveservices", "usage", "list")]
        for call, prefix in zip(command.call_args_list, prefixes):
            arguments = call.args[0]
            self.assertIsInstance(arguments, tuple)
            self.assertEqual(arguments[:len(prefix)], prefix)
            self.assertEqual(arguments[arguments.index("--subscription") + 1], SUBSCRIPTION)
            self.assertEqual(call.kwargs, {"check": True, "capture_output": True, "text": True, "timeout": 60})
        self.assertNotIn("synthetic-quota", output.getvalue())

    def test_cli_errors_are_redacted_and_preserve_files(self):
        for failure in (OSError("private CLI diagnostic"),
                        subprocess.CalledProcessError(1, "az", output="private CLI diagnostic"),
                        subprocess.TimeoutExpired("az", 60, output="private CLI diagnostic")):
            self.seed()
            before = self.catalog_path.read_bytes(), self.report_path.read_bytes()
            output = io.StringIO()
            with patch.object(sync.subprocess, "run", side_effect=failure), redirect_stdout(output):
                self.assertEqual(sync.main(self.args), 1)
            self.assertNotIn("private CLI diagnostic", output.getvalue())
            self.assertEqual((self.catalog_path.read_bytes(), self.report_path.read_bytes()), before)

    def test_staging_error_does_not_replace_either_output(self):
        self.seed()
        factory = tempfile.NamedTemporaryFile
        with patch.object(sync.tempfile, "NamedTemporaryFile", side_effect=[factory(dir=self.directory, delete=False), OSError("synthetic write failure")]):
            self.assert_preserved_failure()


if __name__ == "__main__":
    unittest.main()
