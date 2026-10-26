"""Execute the real rendered/XML-decoded C# against synthetic ARM GET envelopes.

Fixture shape: Deployments_List, Microsoft.CognitiveServices, API 2024-10-01.
No Azure credentials, network calls, inference, SDK downloads, or client dependencies.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))
from dynamic_model_policy_harness import CompiledPolicy
from test_generate_tfvars import CATALOG_ENV, evaluate_policy_module, generate_tfvars, inventory_configuration, write_policy_module

FIXTURE = json.loads((TEST_DIR / "fixtures/dynamic-models/deployments.json").read_text())
ACCOUNT = FIXTURE["value"][0]["id"].rsplit("/deployments/", 1)[0]
SECONDARY = ACCOUNT.replace("/accounts/foundry", "/accounts/secondary")
URL = "https://management.azure.com" + ACCOUNT + "/deployments?api-version=2024-10-01"
ERROR = '{"error":{"type":"api_error","message":"Model inventory is temporarily unavailable."}}'


def deployment(name="claude-opus-pinned", model="claude-opus-5-5", account=ACCOUNT, state="Succeeded", format="Anthropic"):
    row = copy.deepcopy(FIXTURE["value"][0])
    row.update(name=name, id=account + "/deployments/" + name)
    row["properties"].update(provisioningState=state)
    row["properties"]["model"].update(name=model, format=format)
    return row


def page(rows=(), next_link=None, **response):
    return dict(body={"value": list(rows), "nextLink": next_link}, **response)


def link(token="page2"):
    return URL + "&$skiptoken=" + token


def resolve_named_values(policy, desktop=False):
    # Same named-value substitution APIM performs; the policy C# itself is unchanged.
    values = {"required-app-role": "Gateway.User", "claude-desktop-delegated-auth-enabled": str(desktop).lower(),
              "claude-desktop-client-id": "desktop-client", "claude-desktop-delegated-scope": "Gateway.Access",
              "per-user-rate-limit": "100"}
    for name, value in values.items():
        policy = policy.replace("{{" + name + "}}", value)
    return policy


class DynamicModelPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("tofu"):
            raise RuntimeError("OpenTofu is required to render the actual policy; these tests cannot silently skip")
        with tempfile.TemporaryDirectory(prefix="pr6-render-") as temporary:
            directory = Path(temporary)
            write_policy_module(directory)
            with patch.dict(os.environ, CATALOG_ENV, clear=True):
                inputs = generate_tfvars.values()

            def render(values):
                result = evaluate_policy_module(directory, values)
                if result.returncode or result.stderr:
                    raise RuntimeError(result.stderr)
                return json.loads(json.loads(result.stdout))

            cls.policies = render(dict(inputs, deploy_secondary=True, secondary_foundry_resource_id=SECONDARY))
            cls.configuration = inventory_configuration(cls.policies["primary"])
            greenfield = render(dict(inputs, deployment_mode="greenfield", foundry_account_name="greenfield",
                                     claude_model_deployment_name="claude-one"))["primary"]
            cls.greenfield_account = inventory_configuration(greenfield)["account_resource_id"]
            cls.policies["greenfield"] = greenfield
            cls.policies["desktop"] = resolve_named_values(cls.policies["primary"], desktop=True)
            cls.policies = {key: resolve_named_values(value) for key, value in cls.policies.items()}
        cls.compiled = CompiledPolicy(cls.policies)
        cls.addClassCleanup(cls.compiled.close)
        probe = cls.compiled.run([{"pages": [page()]}])
        print("C# runtime: " + probe["runtime"] + "; " + probe["newtonsoft"], flush=True)

    def run_requests(self, *requests, cache_enabled=True):
        return self.compiled.run(list(requests), cache_enabled)["results"]

    def data(self, result):
        self.assertEqual(result["status"], 200, result)
        self.assertFalse(result["forwarded"])
        self.assertEqual(result["headers"], {"Content-Type": "application/json", "Cache-Control": "no-store"})
        self.assertNotIn("inference-identity", result["events"])
        return json.loads(result["body"])["data"]

    def unavailable(self, result, calls=1):
        self.assertEqual(result["status"], 503, result)
        self.assertEqual(result["body"], ERROR)
        self.assertEqual(result["headers"], {"Content-Type": "application/json", "Cache-Control": "no-store"})
        self.assertEqual(len(result["calls"]), calls)
        self.assertEqual(result["stores"], 0)
        self.assertFalse(result["forwarded"])

    def test_add_remove_and_complete_empty_inventory_on_the_same_render(self):
        a, b = deployment(), deployment("claude-future", "claude-horizon-9")
        results = self.run_requests(
            {"time": 0, "pages": [page([a])]}, {"time": 29},
            {"time": 30, "pages": [page([b, a])]}, {"time": 59},
            {"time": 60, "pages": [page([b])]},
            {"time": 90, "pages": [page()]}, {"time": 119})
        self.assertEqual([[row["id"] for row in self.data(result)] for result in results],
                         [[a["name"]], [a["name"]], [a["name"], b["name"]], [a["name"], b["name"]], [b["name"]], [], []])
        self.assertEqual([len(result["calls"]) for result in results], [1, 0, 1, 0, 1, 1, 0])
        self.assertEqual([result["stores"] for result in results], [1, 0, 1, 0, 1, 1, 0])
        self.assertEqual(len({result["cache_key"] for result in results}), 1)

    def test_metadata_filter_not_generation_or_deployment_name_filter(self):
        rows = [deployment(), deployment("claude-sonnet-pinned", "claude-sonnet-99-7"),
                deployment("claude-future", "horizon-12", format="FutureFormat"),
                deployment("custom-route", "novel-family", format="aNtHrOpIc"),
                deployment("claude-openai", "claude-opus-5-5", format="OpenAI"),
                deployment("claude-failed", state="Failed"), deployment("claude-creating", state="Creating")]
        rows[2]["properties"]["model"]["publisher"] = "Anthropic"
        del rows[-1]["properties"]["model"]
        result, = self.run_requests({"pages": [page(rows)]})
        data = self.data(result)
        self.assertEqual([row["id"] for row in data], ["claude-opus-pinned", "claude-sonnet-pinned", "claude-future", "custom-route"])
        for row in data:
            self.assertEqual(row["display_name"], row["id"])
            self.assertLessEqual(set(row), {"id", "display_name", "anthropic_family_tier", "is_family_default"})
        self.assertEqual(data[1]["anthropic_family_tier"], "sonnet")
        self.assertTrue(data[1]["is_family_default"])
        self.assertNotIn("anthropic_family_tier", data[2])
        self.assertNotIn("anthropic_family_tier", data[3])
        for private in ("subscriptions", "sku", "version", "not-public", "capabilities", "publisher"):
            self.assertNotIn(private, result["body"])

    def test_present_pins_first_other_ids_stable_and_absent_pins_not_fabricated(self):
        rows = [deployment("claude-sonnet-old", "claude-3-5-sonnet"), deployment("claude-haiku-pinned", "claude-haiku-4-5"),
                deployment("claude-sonnet-pinned", "claude-sonnet-4-5"), deployment(), deployment("claude-aaa", "claude-horizon")]
        first, missing = self.run_requests({"pages": [page(rows)]}, {"time": 30, "pages": [page([rows[0], rows[-1]])]})
        self.assertEqual([row["id"] for row in self.data(first)], ["claude-opus-pinned", "claude-sonnet-pinned", "claude-haiku-pinned", "claude-aaa", "claude-sonnet-old"])
        self.assertEqual([row["id"] for row in self.data(missing)], ["claude-aaa", "claude-sonnet-old"])
        self.assertFalse(self.data(missing)[1]["is_family_default"])

    def test_duplicate_cross_family_pins_do_not_relabel_actual_models(self):
        config = copy.deepcopy(self.configuration)
        config["pins"] = dict.fromkeys(("opus", "sonnet", "haiku"), "claude-opus-pinned")
        rows = [deployment(), deployment("claude-sonnet-pinned", "claude-sonnet-5"), deployment("claude-haiku-pinned", "claude-haiku-5")]
        result, = self.run_requests({"configuration": config, "pages": [page(rows)]})
        data = self.data(result)
        self.assertEqual(len(data), 3)
        self.assertEqual([row["anthropic_family_tier"] for row in data], ["opus", "haiku", "sonnet"])
        self.assertEqual([row["is_family_default"] for row in data], [True, False, False])
        wrong_name = deployment("claude-sonnet-pinned", "claude-opus-5-5")
        result, = self.run_requests({"pages": [page([wrong_name])]})
        self.assertEqual(self.data(result)[0]["anthropic_family_tier"], "opus")
        self.assertFalse(self.data(result)[0]["is_family_default"])

    def test_deployment_names_use_existing_syntax_without_an_invented_length_limit(self):
        name = "claude-" + "a" * 80
        config = copy.deepcopy(self.configuration)
        config["pins"]["opus"] = name
        result, = self.run_requests({"configuration": config, "pages": [page([deployment(name)])]})
        self.assertEqual(self.data(result)[0]["id"], name)
        self.assertTrue(self.data(result)[0]["is_family_default"])

    def test_complete_one_two_and_three_page_inventories(self):
        a, b, c = deployment(), deployment("claude-sonnet-pinned", "claude-sonnet-5"), deployment("claude-haiku-pinned", "claude-haiku-5")
        for pages, expected in (([page([a])], [a["name"]]),
                                ([page([a], link()), page([b])], [a["name"], b["name"]]),
                                ([page([c], link()), page([a], link("page3")), page([b])], [a["name"], b["name"], c["name"]])):
            with self.subTest(pages=len(pages)):
                result, = self.run_requests({"pages": pages})
                self.assertEqual([row["id"] for row in self.data(result)], expected)
                self.assertEqual(len(result["calls"]), len(pages))
                self.assertEqual(result["stores"], 1)
                self.assertEqual(result["events"].count("continuation-delay:1"), int(len(pages) == 3))
                self.assertGreater(result["events"].index("cache-store"), max(i for i, value in enumerate(result["events"]) if value == "ARM"))

    def test_opaque_continuation_encoding_is_preserved_without_caller_data(self):
        suffixes = ["api-version=2024-10-01&$skiptoken=A%2BB%2FC%3D%3D",
                    "%24skipToken=A%252B%26B%3D&api-version=2024-10-01",
                    "api-version=2024-10-01&$skiptoken=A+B/C=="]
        for suffix in suffixes:
            with self.subTest(suffix=suffix):
                next_link = "https://MANAGEMENT.AZURE.COM:443" + ACCOUNT + "/deployments?" + suffix
                result, = self.run_requests({"query": "limit=1000&api-version=evil&nextLink=https://evil.invalid",
                    "headers": {"Authorization": "caller-only", "api-key": "caller-only", "X-Arbitrary": "caller-only"},
                    "pages": [page([], next_link), page([deployment()])]})
                self.data(result)
                self.assertEqual(result["calls"][0]["url"], URL)
                self.assertEqual(result["calls"][1]["url"], "https://management.azure.com" + ACCOUNT + "/deployments?" + suffix)
                for call in result["calls"]:
                    self.assertEqual((call["mode"], call["method"], call["timeout"]), ("new", "GET", "2"))
                    self.assertEqual(call["headers"], {"Accept": "application/json"})
                    self.assertEqual(call["identity_resource"], "https://management.azure.com/")

    def test_unsafe_next_links_rejected_before_another_identity_request(self):
        invalid = [link().replace("https:", "http:"), link().replace("management.azure.com", "evil.invalid"),
                   link().replace("management.azure.com", "management.azure.com.evil.invalid"),
                   link().replace("management.azure.com", "user@management.azure.com"),
                   link().replace("management.azure.com", "management.azure.com:444"),
                   link().replace("management.azure.com", "management.azure.com."),
                   link() + "#", link() + "#fragment", "/deployments?api-version=2024-10-01&$skiptoken=x",
                   link().replace("https:", ""), link().replace("/accounts/foundry/", "/accounts/other/"),
                   link().replace("/deployments?", "/models?"), link().replace("/deployments?", "/deployments/?"),
                   link().replace("/deployments?", "/x/../deployments?"),
                   link().replace("/deployments?", "/%2e/deployments?"),
                   link().replace("/accounts/", "%2faccounts/"), link().replace("/accounts/", "%252faccounts/"),
                   link().replace("/accounts/", "\\accounts/"), link() + "&api-version=2024-10-01",
                   link() + "&%61pi-version=2024-10-01", link() + "&%24skipToken=another",
                   link().replace("2024-10-01", "2025-01-01"), URL, link() + "&$top=100",
                   link().replace("$skiptoken", "unknown"), link().replace("$skiptoken", "skiptoken"),
                   link(""), link("%GG"), link("a%00b"), link("a%0d%0ab"), link("a;b=c"), " " + link(), link() + "\n", link("a" * 8192)]
        results = self.run_requests(*({"time": i * 30, "pages": [page([deployment()], value)]} for i, value in enumerate(invalid)))
        for value, result in zip(invalid, results):
            with self.subTest(next_link=value):
                self.unavailable(result)

    def test_cycles_detected_across_token_encoding_and_query_order(self):
        first = link("A%2BB%2FC%3D")
        repeated = "https://management.azure.com:443" + ACCOUNT + "/deployments?%24skipToken=%41%2bB%2fC%3d&api-version=2024-10-01"
        for second in (first, repeated):
            with self.subTest(next_link=second):
                result, = self.run_requests({"pages": [page([], first), page([], second)]})
                self.unavailable(result, calls=2)

    def test_incomplete_fourth_page_is_never_requested_or_cached(self):
        result, = self.run_requests({"pages": [page([deployment()], link("2")), page([], link("3")), page([], link("4"))]})
        self.unavailable(result, calls=3)

    def test_arm_status_timeout_and_identity_errors_are_fixed_redacted_failures(self):
        failures = [{"status": status, "body": "ARM private URL subscription token exception"} for status in (204, 302, 400, 401, 403, 429, 500, 503)]
        failures += [{"networkError": True}, {"identityError": True}, {"body": None}]
        results = self.run_requests(*({"time": i * 30, "pages": [failure]} for i, failure in enumerate(failures)))
        for result in results:
            self.unavailable(result)

    def test_later_page_failure_no_partial_cache_and_no_stale_fallback(self):
        results = self.run_requests(
            {"time": 0, "pages": [page([deployment()])]},
            {"time": 30, "pages": [page([deployment("claude-new")], link()), {"status": 403, "body": "private"}]},
            {"time": 31, "pages": [{"networkError": True}]},
            {"time": 32, "pages": [page()]})
        self.data(results[0])
        self.unavailable(results[1], calls=2)
        self.unavailable(results[2])
        self.assertEqual(self.data(results[3]), [])

    def test_later_http_and_transport_failures_never_retry_or_cache(self):
        failures = [{"status": 503, "body": "private"}, {"networkError": True}, {"identityError": True}]
        results = self.run_requests(*({"time": i * 30, "pages": [page([], link()), failure]}
                                     for i, failure in enumerate(failures)))
        for result in results:
            self.unavailable(result, calls=2)
            self.assertNotIn("continuation-delay:1", result["events"])

    def test_continuation_delay_rechecks_budget_but_two_page_completion_does_not_wait(self):
        delayed, complete = self.run_requests(
            {"pages": [page([], link(), elapsedSeconds=2), page([], link("3"), elapsedSeconds=2.2)]},
            {"time": 30, "pages": [page([], link(), elapsedSeconds=2), page([], elapsedSeconds=2.2)]})
        self.unavailable(delayed, calls=2)
        self.assertEqual(delayed["events"].count("continuation-delay:1"), 1)
        self.assertEqual(self.data(complete), [])
        self.assertEqual((len(complete["calls"]), complete["stores"]), (2, 1))
        self.assertNotIn("continuation-delay:1", complete["events"])

    def test_elapsed_budget_checked_before_fetch_after_fetch_and_before_cache(self):
        results = self.run_requests(
            {"elapsedBeforeFetch": 5},
            {"time": 30, "pages": [page([deployment()], elapsedSeconds=5)]},
            {"time": 60, "pages": [page([], link(), elapsedSeconds=3), page([], elapsedSeconds=3)]},
            {"time": 90, "pages": [page([], link(), elapsedSeconds=1), page([], link("3"), elapsedSeconds=1), page([], elapsedSeconds=1)]})
        for result, calls in zip(results[:3], (0, 1, 2)):
            self.unavailable(result, calls=calls)
        self.assertEqual(self.data(results[3]), [])

    def test_total_row_limit_counts_all_pages_and_non_anthropic_rows(self):
        rows = [deployment("claude-row-" + str(i), format="OpenAI") for i in range(1001)]
        results = self.run_requests(
            {"pages": [page(rows[:1000])]}, {"time": 30, "pages": [page(rows)]},
            {"time": 60, "pages": [page(rows[:500], link()), page(rows[500:])]})
        self.assertEqual(self.data(results[0]), [])
        self.unavailable(results[1])
        self.unavailable(results[2], calls=2)

    def test_page_string_and_utf8_byte_bounds(self):
        prefix, suffix = '{"value":[],"padding":"', '"}'
        exact = prefix + "x" * (1048576 - len(prefix + suffix)) + suffix
        too_many_bytes = prefix + "é" * 524288 + suffix
        results = self.run_requests(
            {"pages": [{"body": exact}]}, {"time": 30, "pages": [{"body": exact + " "}]},
            {"time": 60, "pages": [{"body": too_many_bytes}]},
            {"time": 90, "pages": [{"body": prefix + "x" * 524288 + suffix, "utf16Body": True}]})
        self.assertEqual(self.data(results[0]), [])
        self.unavailable(results[1])
        self.unavailable(results[2])
        self.unavailable(results[3])

    def test_malformed_envelopes_and_succeeded_rows_fail_closed(self):
        bodies = ["not-json", "[]", "{", {}, {"value": None}, {"value": {}}, {"data": []},
                  {"value": [None]}, {"value": ["deployment"]}, {"value": [], "nextLink": 7}]
        mutations = [lambda row: row.pop("id"), lambda row: row.update(id=SECONDARY + "/deployments/" + row["name"]),
                     lambda row: row.update(id=row["id"] + "-other"), lambda row: row.update(name="../claude"),
                     lambda row: row.update(name=["claude"]), lambda row: row.pop("type"),
                     lambda row: row.update(type="another/type"), lambda row: row.pop("properties"),
                     lambda row: row["properties"].pop("provisioningState"),
                     lambda row: row["properties"].update(provisioningState=7),
                     lambda row: row["properties"].pop("model"), lambda row: row["properties"]["model"].pop("name"),
                     lambda row: row["properties"]["model"].update(name=" "),
                     lambda row: row["properties"]["model"].update(format=None),
                     lambda row: row["properties"]["model"].update(format=[]),
                     lambda row: row["properties"]["model"].update(publisher={})]
        for mutate in mutations:
            row = deployment()
            mutate(row)
            bodies.append({"value": [row]})
        results = self.run_requests(*({"time": i * 30, "pages": [{"body": body}]} for i, body in enumerate(bodies)))
        for body, result in zip(bodies, results):
            with self.subTest(body=body):
                self.unavailable(result)

    def test_duplicate_ids_case_insensitive_and_across_pages(self):
        a, same, case = deployment(), deployment(), deployment("CLAUDE-OPUS-PINNED")
        results = self.run_requests({"pages": [page([a, same])]},
            {"time": 30, "pages": [page([a, case])]},
            {"time": 60, "pages": [page([a], link()), page([case])]})
        for result, calls in zip(results, (1, 1, 2)):
            self.unavailable(result, calls=calls)

    def test_runtime_configuration_validation_happens_before_cache_or_identity(self):
        invalid = [ACCOUNT + value for value in ("?url=x", "#fragment", "/../other", "%2fother", "\\other", "\n")]
        invalid += [ACCOUNT.replace("/foundry-rg/", "/../"), ACCOUNT.replace("/foundry-rg/", "/a%2fb/"),
                    ACCOUNT.replace("/foundry-rg/", "/a b/"), ACCOUNT.replace("/accounts/foundry", "/accounts/..")]
        configs = [{**self.configuration, "account_resource_id": value} for value in invalid]
        configs += [{}, {"account_resource_id": []}, {**self.configuration, "pins": {"opus": "missing-roles"}},
                    {**self.configuration, "pins": dict.fromkeys(("opus", "sonnet", "haiku"), 'claude-"<{{inject}}')},
                    {**self.configuration, "extra": "x" * 16384}]
        results = self.run_requests(*({"configuration": config} for config in configs))
        for config, result in zip(configs, results):
            with self.subTest(configuration=str(config)[:250]):
                self.unavailable(result, calls=0)
                self.assertEqual(result["lookups"], 0)

    def test_resource_group_unicode_and_punctuation_are_uri_encoded_not_rejected(self):
        account = ACCOUNT.replace("/foundry-rg/", "/Grüppe_(東).test/")
        config = {**self.configuration, "account_resource_id": account}
        result, = self.run_requests({"configuration": config, "pages": [page([deployment(account=account)])]})
        self.data(result)
        url = result["calls"][0]["url"]
        self.assertEqual(unquote(urlsplit(url).path), account + "/deployments")
        self.assertNotIn("ü", url)
        self.assertNotIn("東", url)

    def test_auth_and_per_user_limit_precede_cache_and_arm(self):
        results = self.run_requests(
            {"pages": [page()]}, {"auth": "missing"}, {"auth": "invalid"}, {"auth": "denied"},
            {"claims": {"oid": []}}, {"denyUserRate": True})
        self.data(results[0])
        for result, status in zip(results[1:], (401, 401, 403, 401, 429)):
            self.assertEqual(result["status"], status)
            self.assertEqual((result["lookups"], result["stores"], result["calls"]), (0, 0, []))
        events = results[0]["events"]
        self.assertLess(events.index("authenticate"), events.index("cache-lookup"))
        self.assertLess(next(i for i, value in enumerate(events) if value.startswith("rate:claude-foundry:models:rpm:")), events.index("cache-lookup"))

    def test_configured_desktop_authorization_remains_role_or_scope(self):
        results = self.run_requests({"policy": "desktop", "auth": "desktop", "pages": [page()]},
            {"policy": "desktop", "auth": "desktop", "claims": {"azp": ["wrong-client"]}},
            {"policy": "desktop", "auth": "desktop", "claims": {"scp": ["wrong-scope"]}},
            {"auth": "desktop"})
        self.data(results[0])
        for result in results[1:]:
            self.assertEqual(result["status"], 403)
            self.assertEqual(result["lookups"], 0)
            self.assertEqual(result["calls"], [])

    def test_post_is_independent_of_inventory_outage_and_keeps_credential_stripping(self):
        results = self.run_requests({"pages": [{"status": 403, "body": "private"}]},
            {"method": "POST", "operation": "messages", "headers": {"Authorization": "caller", "x-api-key": "caller", "api-key": "caller", "Ocp-Apim-Subscription-Key": "caller", "x-functions-key": "caller"}},
            {"method": "POST", "operation": "count-tokens"}, {"method": "POST", "operation": "models"})
        self.unavailable(results[0])
        for result in results[1:]:
            self.assertTrue(result["forwarded"])
            self.assertEqual(result["status"], 200)
            self.assertEqual((result["calls"], result["lookups"], result["stores"]), ([], 0, 0))
            self.assertIn("inference-identity", result["events"])
            self.assertEqual(result["events"].count("inference-concurrency"), 2)
        self.assertEqual(results[1]["request_headers"], {"Authorization": "Bearer synthetic-inference-token"})

    def test_account_keyed_miss_admission_is_separate_from_pins_and_inference(self):
        requests = []
        for i in range(11):
            config = copy.deepcopy(self.configuration)
            config["pins"]["opus"] = "claude-pin-" + str(i)
            requests.append({"user": "user-" + str(i), "configuration": config, "pages": [page()] if i < 10 else []})
        requests += [{"policy": "secondary", "pages": [page()]}, {"method": "POST", "operation": "messages"},
                     {"time": 10, "pages": [page()]}]
        results = self.run_requests(*requests, cache_enabled=False)
        for result in results[:10]:
            self.assertEqual(self.data(result), [])
        self.unavailable(results[10], calls=0)
        self.data(results[11])
        self.assertTrue(results[12]["forwarded"])
        self.data(results[13])

    def test_cache_and_url_bindings_isolate_secondary_greenfield_and_pin_changes(self):
        changed = copy.deepcopy(self.configuration)
        changed["pins"]["opus"] = "claude-other-pin"
        results = self.run_requests(
            {"pages": [page([deployment()])]}, {"configuration": changed, "pages": [page()]},
            {"policy": "secondary", "pages": [page([deployment(account=SECONDARY)])]},
            {"policy": "greenfield", "pages": [page([deployment("claude-one", account=self.greenfield_account)])]})
        self.assertEqual(len({result["cache_key"] for result in results}), 4)
        for result, account in zip(results, (ACCOUNT, ACCOUNT, SECONDARY, self.greenfield_account)):
            self.data(result)
            self.assertEqual(result["calls"][0]["url"], "https://management.azure.com" + account + "/deployments?api-version=2024-10-01")
        self.assertEqual(self.data(results[-1]), [{"id": "claude-one", "display_name": "claude-one", "anthropic_family_tier": "opus", "is_family_default": True}])


if __name__ == "__main__":
    unittest.main()
