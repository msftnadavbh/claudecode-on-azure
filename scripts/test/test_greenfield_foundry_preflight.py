#!/usr/bin/env python3
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import greenfield_foundry_preflight

ARGS = ["--subscription", "sub", "--resource-group", "new-rg", "--location", "eastus", "--model", "claude", "--version", "1", "--sku", "GlobalStandard", "--capacity", "5"]
CATALOG = [{
    "kind": "AIServices",
    "model": {
        "format": "Anthropic",
        "name": "claude",
        "version": "1",
        "capabilities": {"streaming": "true"},
        "skus": [{"name": "GlobalStandard", "usageName": "Claude Global Standard"}],
    },
    "skuName": "S0",
}]


class GreenfieldPreflightTests(unittest.TestCase):
    def invoke(self, responses):
        output = io.StringIO()
        with patch("greenfield_foundry_preflight.subprocess.run", side_effect=lambda *_, **__: SimpleNamespace(stdout=json.dumps(next(responses)))), redirect_stdout(output):
            code = greenfield_foundry_preflight.main(ARGS)
        return code, json.loads(output.getvalue())

    def test_success(self):
        code, report = self.invoke(iter([{"id": "sub"}, False, CATALOG, [{"name": {"value": "Claude Global Standard"}, "currentValue": 2, "limit": 10}]]))
        self.assertEqual(code, 0)
        self.assertEqual(report["model"]["usage_name"], "Claude Global Standard")

    def test_rejects_existing_resource_group(self):
        code, report = self.invoke(iter([{"id": "sub"}, True]))
        self.assertEqual(code, 1)
        self.assertIn("already exists", report["errors"][0])

    def test_rejects_unavailable_sku_or_model(self):
        code, report = self.invoke(iter([{"id": "sub"}, False, []]))
        self.assertEqual(code, 1)
        self.assertIn("unavailable", report["errors"][0])

    def test_rejects_missing_usage_name(self):
        catalog = [{**CATALOG[0], "model": {**CATALOG[0]["model"], "skus": [{"name": "GlobalStandard"}]}}]
        code, report = self.invoke(iter([{"id": "sub"}, False, catalog]))
        self.assertEqual(code, 1)
        self.assertIn("usageName", report["errors"][0])

    def test_rejects_insufficient_quota(self):
        code, report = self.invoke(iter([{"id": "sub"}, False, CATALOG, [{"name": {"value": "Claude Global Standard"}, "currentValue": 8, "limit": 10}]]))
        self.assertEqual(code, 1)
        self.assertIn("below requested", report["errors"][0])

    def test_rejects_non_azure_hosted_model(self):
        catalog = [{**CATALOG[0], "kind": "MaaS"}]
        code, report = self.invoke(iter([{"id": "sub"}, False, catalog]))
        self.assertEqual(code, 1)
        self.assertIn("unavailable", report["errors"][0])

    def test_ignores_top_level_account_sku(self):
        catalog = [{"kind": "AIServices", "model": {**CATALOG[0]["model"], "skus": []}, "skuName": "GlobalStandard", "usageName": "Wrong"}]
        code, report = self.invoke(iter([{"id": "sub"}, False, catalog]))
        self.assertEqual(code, 1)
        self.assertIn("unavailable", report["errors"][0])

    def test_allows_existing_resource_group_only_with_explicit_flag(self):
        output = io.StringIO()
        responses = iter([{"id": "sub"}, CATALOG, [{"name": {"value": "Claude Global Standard"}, "currentValue": 2, "limit": 10}]])
        with patch("greenfield_foundry_preflight.subprocess.run", side_effect=lambda *_, **__: SimpleNamespace(stdout=json.dumps(next(responses)))), redirect_stdout(output):
            code = greenfield_foundry_preflight.main([*ARGS, "--allow-existing-resource-group"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
