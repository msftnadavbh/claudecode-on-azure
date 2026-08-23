#!/usr/bin/env python3
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tofu"))
import plan_summary


class PlanSummaryTests(unittest.TestCase):
    def test_emits_only_sorted_safe_fields(self):
        result = plan_summary.summarize({"resource_changes": [
            {"address": "azurerm_b.example", "type": "azurerm_b", "change": {"actions": ["update"], "before": {"secret": "no"}}},
            {"address": "azurerm_a.example", "type": "azurerm_a", "change": {"actions": ["create"]}},
        ]})
        self.assertEqual([item["address"] for item in result], ["azurerm_a.example", "azurerm_b.example"])
        self.assertTrue(all(len(item["planned_change_sha256"]) == 64 for item in result))
        self.assertNotIn("secret", str(result))

    def test_rejects_delete_and_replacement(self):
        for actions in (["delete"], ["delete", "create"]):
            with self.subTest(actions=actions):
                with self.assertRaisesRegex(ValueError, "not allowed"):
                    plan_summary.summarize({"resource_changes": [{
                        "address": "azurerm_example.resource", "type": "azurerm_example", "change": {"actions": actions},
                    }]})


if __name__ == "__main__":
    unittest.main()
