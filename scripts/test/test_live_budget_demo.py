"""Offline only: no Azure CLI, Windows helper, DNS or cloud calls."""

import base64
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import xml.etree.ElementTree as ET

import live_budget_demo as demo


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "state"
        self.output = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.output))
        self.enterContext(patch.object(demo, "STATE_ROOT", self.root))
        # Any accidentally unmocked transport/helper is a test failure, never a live call.
        self.transport = self.enterContext(patch.object(demo.urllib.request, "build_opener", side_effect=AssertionError("network forbidden")))
        self.process = self.enterContext(patch.object(demo.subprocess, "run", side_effect=AssertionError("helper forbidden")))
        self.enterContext(patch.object(demo.time, "sleep"))

    def mocked_run(self, fault=None, enter=None):
        enter = enter or self.enterContext
        self.current = None
        self.etag = '"1"'
        self.requests = []
        self.mutations = []
        self.count = 0

        def rest(method, url, credential, body=None, headers=None):
            if url.startswith("https://management.azure.com"):
                self.assertEqual(url.split("?")[0], "https://management.azure.com" + demo.POLICY)
                if method == "PUT":
                    self.assertEqual(headers, {"If-None-Match": "*"})
                    self.assertEqual(body["properties"]["format"], "rawxml")
                    run_id = ET.fromstring(body["properties"]["value"]).find("outbound/set-header/value").text
                    directory = self.root / run_id
                    state = demo.load(directory)
                    self.assertEqual(state["candidate"], body["properties"]["value"])
                    self.assertGreater(state["deadline"], demo.time.time())
                    self.current = body["properties"]["value"]
                    self.mutations.append("PUT")
                    if fault == "ambiguous_put":
                        raise TimeoutError("SECRET ambiguous accepted mutation")
                    return 201, {}, {}
                if method == "DELETE":
                    self.assertEqual(headers, {"If-Match": '"1"'})
                    self.mutations.append("DELETE")
                    if fault == "delete_412":
                        return 412, {}, {"error": {"code": "PreconditionFailed", "message": "SECRET"}}
                    self.current = None
                    return 204, {}, {}
                return ((200, {"etag": self.etag}, {"properties": {"value": self.current}})
                        if self.current else (404, {}, {}))
            self.requests.append((url, body, credential))
            self.assertLessEqual(len(json.dumps(body).encode()), 3000)
            self.assertNotIn("tools", body)
            self.assertEqual(body["model"], demo.MODEL)
            if url.endswith("/count_tokens"):
                return 200, {}, {"input_tokens": demo.MIN_INPUT - 1 if fault == "count" else demo.MAX_INPUT + 1 if fault == "count_high" else 494}
            self.assertEqual(body["max_tokens"], 8)
            self.assertIs(body["stream"], False)
            if not self.current:
                return 200, {}, {"usage": {"input_tokens": 10, "output_tokens": 2}}
            self.count += 1
            if fault == "interrupt":
                raise KeyboardInterrupt
            marker = ET.fromstring(self.current).find("outbound/set-header/value").text
            if fault == "etag_drift":
                self.etag = '"2"'
                raise RuntimeError("SECRET")
            if fault == "policy_drift":
                self.current = "<policies />"
                raise RuntimeError("SECRET")
            if ((self.count == 3 and fault not in {"fourth_denied", "fourth_success", "fourth_auth403"})
                    or (self.count == 4 and fault != "fourth_success")):
                if fault == "overflow":
                    return 200, {}, {"usage": {"input_tokens": 494, "output_tokens": 8}}
                if fault in {"auth403", "fourth_auth403"}:
                    return 403, {demo.REMAINING: "76"}, {"message": "Pilot access not assigned."}
                if fault == "quota_code":
                    return 403, {}, {"error": {"code": "TokenQuotaExceeded"}}
                if fault == "quota_text_only":
                    return 403, {}, {"message": "Token quota exceeded. SECRET"}
                return 403, {demo.RETRY: "60", demo.REMAINING: "-76", demo.CONSUMED: "0"}, {
                    "statusCode": 403, "message": "Token quota exceeded. SECRET"}
            return 200, ({demo.MARKER: marker} if fault == "missing_headers" else {
                demo.MARKER: marker, demo.REMAINING: str(-10 + self.count if fault == "odd_estimates" else demo.QUOTA - self.count * 502),
                demo.CONSUMED: "0" if fault == "odd_estimates" else "502"}), {
                    "usage": {"input_tokens": 494, "output_tokens": 8}, "content": [{"text": "SECRET"}]}

        enter(patch.object(demo, "http", side_effect=rest))
        self.tokens = enter(patch.object(demo, "token", side_effect=lambda resource=demo.AUD, windows=False, min_ttl=900:
                                     "arm" if resource != demo.AUD else "windows" if windows else "linux"))
        self.context = {demo.API + "/policies/policy": "a" * 64}
        self.snapshots = enter(patch.object(demo, "snapshot", return_value=self.context))

    def test_success_exact_scope_and_five_requests(self):
        self.mocked_run()
        demo.run()
        self.assertEqual(self.mutations, ["PUT", "DELETE"])
        self.assertEqual(len(self.requests), 5)
        self.assertEqual([r[2] for r in self.requests], ["linux", "linux", "windows", "linux", "linux"])
        self.assertEqual(self.requests[1][1], self.requests[2][1])
        self.assertEqual(self.requests[1][1], self.requests[3][1])
        directory = next(self.root.iterdir())
        self.assertTrue(demo.load(directory)["restored"])
        self.assertNotIn("SECRET", self.output.getvalue())
        self.assertIn('"proof": "admission_blocked"', self.output.getvalue())
        self.assertIn('"input_tokens": 494', self.output.getvalue())
        self.assertIn('"x-demo-tokens-consumed": 502', self.output.getvalue())
        self.assertIn('"x-demo-tokens-remaining": 20', self.output.getvalue())
        self.tokens.assert_any_call("https://management.azure.com/", min_ttl=120)
        self.tokens.assert_any_call(min_ttl=120)

    def test_failures_restore_without_inference_retries(self):
        for fault in ("ambiguous_put", "missing_headers", "interrupt", "auth403", "overflow",
                      "fourth_success", "fourth_auth403", "quota_text_only"):
            with self.subTest(fault=fault), contextlib.ExitStack() as stack:
                self.mocked_run(fault, stack.enter_context)
                with self.assertRaises(BaseException):
                    demo.run()
                self.assertEqual(self.mutations, ["PUT", "DELETE"])
                self.assertIsNone(self.current)
                self.assertLessEqual(len(self.requests), 6)
                self.assertNotIn('"proof": "admission_blocked"', self.output.getvalue())

    def test_third_success_fourth_denial_bounded_to_six_requests(self):
        self.mocked_run("fourth_denied")
        demo.run()
        self.assertEqual(len(self.requests), 6)
        self.assertEqual(self.count, 4)
        self.assertTrue(all(request[1] == self.requests[1][1] for request in self.requests[1:5]))
        self.assertIn('"proof": "admission_blocked"', self.output.getvalue())

    def test_odd_native_estimates_are_observations_not_accounting(self):
        self.mocked_run("odd_estimates")
        demo.run()
        self.assertIn('"x-demo-tokens-remaining": -9', self.output.getvalue())
        self.assertIn('"x-demo-tokens-remaining": -8', self.output.getvalue())
        self.assertIn('"x-demo-tokens-consumed": 0', self.output.getvalue())

    def test_native_code_denial_without_any_quota_headers(self):
        self.mocked_run("quota_code")
        demo.run()
        self.assertIn('"proof": "admission_blocked"', self.output.getvalue())

    def test_count_range_aborts_before_mutation(self):
        self.mocked_run("count")
        with self.assertRaisesRegex(RuntimeError, "count_outside"):
            demo.run()
        self.assertEqual(self.mutations, [])
        self.assertFalse(self.root.exists())

    def test_high_count_aborts_before_mutation(self):
        self.mocked_run("count_high")
        with self.assertRaisesRegex(RuntimeError, "count_outside"):
            demo.run()
        self.assertEqual(self.mutations, [])
        self.assertFalse(self.root.exists())

    def test_pre_put_abort_keeps_original_error_without_cleanup(self):
        for fault in ("context", "absence", "deadline"):
            with self.subTest(fault=fault), contextlib.ExitStack() as stack:
                self.mocked_run(enter=stack.enter_context)
                if fault == "context":
                    self.snapshots.side_effect = [self.context, {**self.context, demo.API: "changed"}]
                elif fault == "absence":
                    original = demo.arm
                    calls = 0
                    def absent_then_present(*args, **kwargs):
                        nonlocal calls
                        if args[1] == demo.POLICY and len(args) == 2:
                            calls += 1
                            if calls == 2:
                                return 200, {}, {}
                        return original(*args, **kwargs)
                    stack.enter_context(patch.object(demo, "arm", side_effect=absent_then_present))
                else:
                    now = demo.time.time()
                    stack.enter_context(patch.object(demo.time, "time", side_effect=[now, now + 601]))
                with self.assertRaisesRegex(demo.DemoError, "deadline_exceeded" if fault == "deadline" else "pre_put_drift"):
                    demo.run()
                self.assertEqual(self.mutations, [])
                self.assertEqual(len(self.requests), 1)
                directory = next(self.root.iterdir())
                state = demo.load(directory)
                self.assertEqual(state["phase"], "aborted-before-put")
                self.assertFalse(state["restored"])
                self.assertNotIn('"restored": true', self.output.getvalue())
                self.assertEqual(self.tokens.call_count, 3)
                demo.restored(directory, state)
                self.assertEqual(self.tokens.call_count, 3)
                self.assertEqual(self.mutations, [])

    def test_etag_drift_never_deleted(self):
        self.mocked_run("etag_drift")
        with self.assertRaisesRegex(RuntimeError, "restore_failed"):
            demo.run()
        self.assertEqual(self.mutations, ["PUT"])
        self.assertIn('"manual_recovery_required": true', self.output.getvalue())

    def test_structure_drift_never_deleted(self):
        self.mocked_run("policy_drift")
        with self.assertRaisesRegex(RuntimeError, "restore_failed"):
            demo.run()
        self.assertEqual(self.mutations, ["PUT"])

    def test_delete_race_fails_closed(self):
        self.mocked_run("delete_412")
        with self.assertRaisesRegex(RuntimeError, "restore_failed"):
            demo.run()
        self.assertIsNotNone(self.current)
        self.assertNotIn("SECRET", self.output.getvalue())
        self.assertIn("PreconditionFailed", self.output.getvalue())

    def test_scope_guards_and_policy_structure(self):
        for path in (demo.API, demo.SERVICE, demo.POLICY + "/extra", demo.DEPLOYMENT):
            with self.assertRaisesRegex(RuntimeError, "mutation_scope"):
                demo.arm("unused", path, "PUT")
        with self.assertRaisesRegex(RuntimeError, "conditional_delete_required"):
            demo.arm("unused", demo.POLICY, "DELETE", headers={"If-Match": "*"})
        run_id = "187e3cc4-f741-46e6-8b6e-9bb808924b11"
        root = ET.fromstring(demo.candidate(run_id))
        for section in root:
            self.assertEqual(section[0].tag, "base")
        limit = root.find("inbound/llm-token-limit")
        self.assertEqual((demo.QUOTA, demo.MIN_INPUT, demo.MAX_INPUT), (1024, 480, 510))
        self.assertEqual(limit.get("token-quota"), str(demo.QUOTA))
        self.assertEqual(limit.get("token-quota-period"), "Monthly")
        self.assertEqual(limit.get("estimate-prompt-tokens"), "true")
        self.assertEqual(limit.get("retry-after-header-name"), demo.RETRY)
        self.assertNotIn("api-schema", limit.attrib)
        self.assertIn(run_id, limit.get("counter-key"))
        self.assertIn('context.Variables["pilotJwt"]', limit.get("counter-key"))
        self.assertIn('GetValueOrDefault("tid", "")', limit.get("counter-key"))
        self.assertIn('GetValueOrDefault("oid", "")', limit.get("counter-key"))
        self.assertEqual([child.tag for child in root.find("on-error")], ["base"])

    def test_claims_and_capture_commands(self):
        claims = {"tid": demo.TENANT, "oid": demo.OID, "aud": demo.AUD, "ver": "1.0", "appid": demo.CLI_APP,
                  "roles": ["Gateway.Invoke"], "scp": "AiGateway.Invoke", "exp": demo.time.time() + 3600}
        def jwt():
            return "abc." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".abc"
        with patch.object(demo, "capture", side_effect=lambda command: jwt()) as capture:
            demo.token()
            self.assertIn("--tenant", capture.call_args.args[0])
            self.assertIn(demo.TENANT, capture.call_args.args[0])
            demo.token(windows=True)
            self.assertEqual(capture.call_args.args[0][0], "powershell.exe")
            self.assertIn("desktop-entra-pilot.cmd", capture.call_args.args[0][-1])
            for field in ("tid", "oid", "aud", "ver", "appid", "roles", "scp", "exp"):
                original = claims[field]
                claims[field] = 0 if field == "exp" else [] if field == "roles" else "wrong"
                with self.assertRaises(RuntimeError):
                    demo.token()
                claims[field] = original

    def test_restore_from_durable_state_and_tampering(self):
        self.mocked_run("etag_drift")
        with self.assertRaises(RuntimeError):
            demo.run()
        directory = next(self.root.iterdir())
        state = demo.load(directory)
        self.assertNotIn("phase", state)  # Missing phase is not a completed pre-PUT abort.
        self.etag = state["etag"]
        with patch.object(demo, "REFERENCE", Path(self.temporary.name) / "missing-reference.xml"):
            demo.restored(directory, state)
        self.snapshots.assert_called_with("arm", expected_policy_digest=state["policy_digest"])
        self.assertEqual(sum(call.args == ("https://management.azure.com/",) for call in self.tokens.call_args_list), 3)
        self.assertTrue(demo.load(directory)["restored"])
        state["target"] = demo.API
        demo.save(directory, state)
        with self.assertRaisesRegex(RuntimeError, "state_guard"):
            demo.load(directory)

    def test_short_cached_token_rejected_for_run_but_accepted_for_restore(self):
        claims = {"tid": demo.TENANT, "oid": demo.OID, "aud": demo.AUD, "ver": "1.0", "appid": demo.CLI_APP,
                  "roles": ["Gateway.Invoke"], "scp": "AiGateway.Invoke", "exp": 1300}
        value = "abc." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".abc"
        with patch.object(demo.time, "time", return_value=1000), patch.object(demo, "capture", return_value=value):
            for resource in (demo.AUD, "https://management.azure.com/"):
                with self.subTest(resource=resource):
                    with self.assertRaisesRegex(demo.DemoError, "token_identity_or_expiry"):
                        demo.token(resource)
                    self.assertEqual(demo.token(resource, min_ttl=120), value)

    def test_http_errors_and_redirects_keep_native_response(self):
        body = b'{"code":"TokenQuotaExceeded","message":"Token quota exceeded. SECRET"}'
        error = urllib.error.HTTPError(demo.GATEWAY, 403, "SECRET", {demo.REMAINING: "76"}, io.BytesIO(body))
        self.transport.side_effect = None
        self.transport.return_value.open.side_effect = error
        status, headers, result = demo.http("POST", demo.GATEWAY, "SECRET")
        self.assertEqual(status, 403)
        self.assertEqual(headers[demo.REMAINING], "76")
        self.assertTrue(demo.safe_error(result)[1])
        request = self.transport.return_value.open.call_args.args[0]
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertIsNone(demo.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other"))
        self.assertNotIn("SECRET", self.output.getvalue())

    def test_execute_ack_required_before_any_side_effect(self):
        for args in (["run"], ["run", "--execute"], ["restore", "--execute"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                demo.main(args)
        self.process.assert_not_called()
        self.transport.assert_not_called()

    def test_fresh_snapshot_hashes_all_context_without_saving_secrets(self):
        reference = "<policies><inbound><base /></inbound></policies>"
        documents = {
            demo.SERVICE: {"sku": {"name": "StandardV2"}},
            demo.API: {"properties": {"path": "claude", "subscriptionRequired": False, "protocols": ["https"]}},
            demo.API + "/policies/policy": {"properties": {"value": reference}},
            demo.API + "/operations": {"value": [
                {"name": "messages", "properties": {"method": "POST", "urlTemplate": "/v1/messages"}},
                {"name": "count-tokens", "properties": {"method": "POST", "urlTemplate": "/v1/messages/count_tokens"}}]},
            demo.SERVICE + "/backends/foundry-claude": {"properties": {
                "url": "https://project-test-01.services.ai.azure.com/anthropic", "credentials": "SECRET"}},
            demo.API + "/products": {"value": [{"name": "pilot"}]},
            demo.SERVICE + "/products/pilot": {"properties": {"displayName": "pilot"}},
            demo.API + "/schemas": {"value": [{"name": "messages"}]},
            demo.API + "/schemas/messages": {"properties": {"document": "SCHEMA"}},
            demo.DEPLOYMENT: {"properties": {"model": {"format": "Anthropic", "name": demo.MODEL, "version": "2"},
                                           "provisioningState": "Succeeded", "versionUpgradeOption": "NoAutoUpgrade"},
                              "sku": {"name": "GlobalStandard", "capacity": 40}},
        }
        def rest(method, url, credential, body=None, headers=None):
            self.assertEqual(method, "GET")
            path = url.removeprefix("https://management.azure.com").split("?")[0]
            if path.endswith("/policies/policy"):
                self.assertTrue(url.endswith("&format=rawxml"))
            return (200, {}, documents[path]) if path in documents else (404, {}, {})
        with patch.object(demo, "http", side_effect=rest), patch.object(Path, "read_text", return_value=reference) as read, \
                patch.object(demo, "REFERENCE_SHA", demo.digest(reference)):
            context = demo.snapshot("unused")
            self.assertEqual(len(context), 13)
            self.assertNotIn("SECRET", json.dumps(context))
            documents[demo.SERVICE]["etag"] = "new"
            documents[demo.SERVICE]["systemData"] = {"lastModifiedAt": "now"}
            documents[demo.API + "/operations"]["value"].reverse()
            for resource in documents[demo.API + "/operations"]["value"]:
                resource["etag"] = "new"
                resource["systemData"] = {"lastModifiedAt": "now"}
            read.side_effect = FileNotFoundError("reference gone")
            self.assertEqual(demo.snapshot("unused", expected_policy_digest=context[demo.API + "/policies/policy"]), context)
            read.side_effect = None
            documents[demo.API + "/policies/policy"]["properties"]["value"] = "<policies />"
            with self.assertRaisesRegex(RuntimeError, "strict_policy_changed"):
                demo.snapshot("unused")
            documents[demo.API + "/policies/policy"]["properties"]["value"] = reference
            documents[demo.API + "/products"]["nextLink"] = "https://other"
            with self.assertRaisesRegex(RuntimeError, "snapshot_pagination_unsupported"):
                demo.snapshot("unused")

    def test_context_drift_after_delete_is_not_reported_restored(self):
        self.mocked_run()
        with patch.object(demo, "snapshot", side_effect=[self.context, self.context, {**self.context, demo.API: "changed"}]):
            with self.assertRaisesRegex(RuntimeError, "restore_failed"):
                demo.run()
        self.assertIsNone(self.current)
        self.assertNotIn('"restored": true', self.output.getvalue())
        self.assertIn('"context_drift_paths": ["' + demo.API + '"]', self.output.getvalue())

    def test_normalization_preserves_configuration_arrays_and_fields(self):
        config = {"properties": {"etag": "config", "systemData": "config", "value": [{"name": "z"}, {"name": "a"}]}}
        self.assertEqual(demo.normalize(config), config)
        self.assertNotEqual(demo.policy_digest("<policies><inbound/><outbound/></policies>"),
                            demo.policy_digest("<policies><outbound/><inbound/></policies>"))

    def test_nonobject_and_invalid_json_response_redacted(self):
        self.transport.side_effect = None
        for body in (b'[]', b'null', b'"SECRET"', b'12', b'SECRET'):
            self.transport.return_value.open.side_effect = urllib.error.HTTPError(
                demo.GATEWAY, 403, "SECRET", {}, io.BytesIO(body))
            self.assertEqual(demo.http("POST", demo.GATEWAY, "SECRET")[2], {})
        self.assertIn("response_parse_failed", self.output.getvalue())
        self.assertNotIn("SECRET", self.output.getvalue())

    def test_empty_delete_response_is_not_a_parse_failure(self):
        self.transport.side_effect = None
        self.transport.return_value.open.side_effect = urllib.error.HTTPError(
            demo.GATEWAY, 204, "", {}, io.BytesIO(b""))
        self.assertEqual(demo.http("DELETE", demo.GATEWAY, "SECRET"), (204, {}, {}))
        self.assertNotIn("response_parse_failed", self.output.getvalue())

    def test_sighup_and_sigterm_registered(self):
        with patch.object(demo.signal, "signal") as signal, patch.object(demo, "run"):
            self.assertEqual(demo.main(["run", "--execute", "--clients-idle"]), 0)
            self.assertEqual({call.args[0] for call in signal.call_args_list}, {demo.signal.SIGHUP, demo.signal.SIGTERM})
            with self.assertRaises(KeyboardInterrupt):
                signal.call_args.args[1](demo.signal.SIGHUP, None)


if __name__ == "__main__":
    unittest.main()
