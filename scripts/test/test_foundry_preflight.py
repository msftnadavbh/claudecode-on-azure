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
import foundry_preflight


ARGS = [
    "--subscription", "sub-id", "--resource-group", "foundry-rg", "--account", "foundry-account",
    "--expected-base-url", "https://foundry-custom.services.ai.azure.com/anthropic",
    "--deployment", "opus=opus-deployment", "--deployment", "sonnet=sonnet-deployment",
    "--deployment", "haiku=haiku-deployment",
]


class FoundryPreflightTests(unittest.TestCase):
    def test_success(self):
        responses = iter([
            {"id": "sub-id"},
            {"kind": "AIServices", "endpoint": "https://foundry-account.cognitiveservices.azure.com/", "location": "eastus", "properties": {"customSubDomainName": "foundry-custom"}, "provisioningState": "Succeeded"},
            [{"name": name, "properties": {"provisioningState": "Succeeded", "model": {"format": "Anthropic", "name": model, "version": "2026-01-01"}}, "sku": {"name": "GlobalStandard", "capacity": 10}} for name, model in (("opus-deployment", "claude-opus"), ("sonnet-deployment", "claude-sonnet"), ("haiku-deployment", "claude-haiku"))],
            [{"name": {"value": "Anthropic Claude Tokens"}, "currentValue": 3, "limit": 20, "unit": "Count"}],
        ])
        output = io.StringIO()
        with patch("foundry_preflight.subprocess.run", side_effect=lambda *_, **__: SimpleNamespace(stdout=json.dumps(next(responses)))) as command, redirect_stdout(output):
            self.assertEqual(foundry_preflight.main(ARGS), 0)
        report = json.loads(output.getvalue())
        self.assertTrue(report["ok"])
        self.assertEqual(report["deployments"]["opus"], {"capacity": 10, "deployment": "opus-deployment", "model": "claude-opus", "sku": "GlobalStandard", "version": "2026-01-01"})
        self.assertEqual(report["quota"]["claude_rows"][0]["limit"], 20)
        self.assertEqual(command.call_count, 4)

    def test_rejects_mismatched_expected_host(self):
        responses = iter([
            {"id": "sub-id"},
            {"kind": "AIServices", "location": "eastus", "properties": {"customSubDomainName": "foundry-custom"}, "provisioningState": "Succeeded"},
        ])
        output = io.StringIO()
        args = [*ARGS]
        args[args.index("https://foundry-custom.services.ai.azure.com/anthropic")] = "https://other.services.ai.azure.com/anthropic"
        with patch("foundry_preflight.subprocess.run", side_effect=lambda *_, **__: SimpleNamespace(stdout=json.dumps(next(responses)))) as command, redirect_stdout(output):
            self.assertEqual(foundry_preflight.main(args), 1)
        self.assertIn("not owned", json.loads(output.getvalue())["errors"][0])
        self.assertEqual(command.call_count, 2)

    def test_rejects_account_without_custom_subdomain(self):
        responses = iter([
            {"id": "sub-id"},
            {"kind": "AIServices", "location": "eastus", "provisioningState": "Succeeded"},
        ])
        output = io.StringIO()
        with patch("foundry_preflight.subprocess.run", side_effect=lambda *_, **__: SimpleNamespace(stdout=json.dumps(next(responses)))), redirect_stdout(output):
            self.assertEqual(foundry_preflight.main(ARGS), 1)
        self.assertIn("customSubDomainName", json.loads(output.getvalue())["errors"][0])

    def test_subscription_mismatch(self):
        output = io.StringIO()
        with patch("foundry_preflight.subprocess.run", return_value=SimpleNamespace(stdout='{"id":"other-sub"}')) as command, redirect_stdout(output):
            self.assertEqual(foundry_preflight.main(ARGS), 1)
        self.assertEqual(json.loads(output.getvalue())["ok"], False)
        self.assertIn("Azure subscription context", json.loads(output.getvalue())["errors"][0])
        self.assertEqual(command.call_count, 1)


if __name__ == "__main__":
    unittest.main()
