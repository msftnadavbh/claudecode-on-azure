"""Offline structural evidence only; live Entra/APIM behavior still needs validation."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]

# Policy statement attribute list, not an APIM runtime/compiler substitute:
# https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy
LLM_TOKEN_LIMIT_ATTRIBUTES = {
    "counter-key", "tokens-per-minute", "token-quota", "token-quota-period",
    "estimate-prompt-tokens", "retry-after-header-name", "retry-after-variable-name",
    "remaining-quota-tokens-header-name", "remaining-quota-tokens-variable-name",
    "remaining-tokens-header-name", "remaining-tokens-variable-name",
    "tokens-consumed-header-name", "tokens-consumed-variable-name",
}


def assert_token_limit_attributes(root):
    for policy in root.iter("llm-token-limit"):
        assert set(policy.attrib) <= LLM_TOKEN_LIMIT_ATTRIBUTES, "unsupported llm-token-limit attribute"


class GatewayPolicyTests(unittest.TestCase):
    def test_models_get_returns_inventory_without_falling_through_to_inference(self):
        root = ET.parse(ROOT / "apim/policies/claude-base.xml").getroot()
        models = next(node for node in root.findall("inbound/choose/when")
                      if node.get("condition") == '@(context.Operation.Id == "models" && context.Request.Method == "GET")')
        response = models.find("return-response")
        self.assertIsNotNone(response, "Foundry's Anthropic inference endpoint does not implement GET /v1/models")
        self.assertEqual(response.find("set-status").get("code"), "200")
        self.assertIsNotNone(models.find("cache-lookup-value"))
        page = ET.parse(ROOT / "apim/policies/claude-models-page.xml").getroot()
        request = page.find("when/send-request")
        self.assertEqual(request.get("mode"), "new")
        self.assertEqual(request.findtext("set-method"), "GET")
        self.assertEqual(request.find("authentication-managed-identity").get("resource"), "https://management.azure.com/")

    def test_disabling_collection_preserves_the_reviewed_baseline(self):
        for name in ("docs/operations-runbook.md", "docs/model-discovery.md", "docs/github-configuration.md"):
            with self.subTest(path=name):
                text = (ROOT / name).read_text()
                shutdown = next((line for line in text.splitlines() if line.startswith("To disable")), "")
                self.assertIn("MODEL_DISCOVERY_ENABLED", shutdown)
                self.assertIn("repository-level", shutdown)
                self.assertIn("explicitly to `false`", shutdown)
                self.assertIn("Deleting or unsetting", shutdown)
                self.assertIn("inherits any organization value", shutdown)
                self.assertIn("only if", shutdown)
                self.assertIn("not `true`", shutdown)
                self.assertIn("MODEL_CATALOG_FILE", shutdown)
                self.assertIn("preserve", shutdown.lower())
                self.assertNotIn("or leave it unset", shutdown)
                self.assertNotIn("unset `MODEL_CATALOG_FILE`", shutdown)

    def test_model_authorization_boundary_documentation(self):
        for name in ("docs/security.md", "docs/01-architecture.md", "docs/02-platform-constraints.md"):
            with self.subTest(path=name):
                text = (ROOT / name).read_text().lower()
                self.assertIn("backend-owned", text)
                self.assertIn("role pins", text)
                self.assertIn("not an authorization boundary", text)
                self.assertIn("after the dynamic policy is deployed", text)
                self.assertIn("account deployment administrators", text)
                self.assertIn("automatic publication", text)
                self.assertIn("live pilot remains static", text)
                self.assertIn("model-discovery.md#runtime-inventory-and-authorization-boundary", text)
                self.assertNotIn("allowlists three configured deployment names", text)
                self.assertNotIn("allows only the three configured deployment names", text)

    def test_live_pilot_is_not_claimed_to_have_this_dynamic_source(self):
        readme = (ROOT / "README.md").read_text()
        pilot = readme.split("### Live pilot status", 1)[1].split("## Validate", 1)[0]
        self.assertIn("static reviewed snapshot", pilot)
        self.assertIn("PR6 has not changed it", pilot)
        self.assertIn("These PR6 source changes have not been deployed", readme)

    def test_token_limit_attribute_typo_rejected_in_every_branch(self):
        for path in (ROOT / "apim/policies").glob("*.xml"):
            root = ET.fromstring(path.read_text())
            assert_token_limit_attributes(root)
            for policy in root.iter("llm-token-limit"):
                with self.subTest(path=path, attributes=policy.attrib):
                    original = dict(policy.attrib)
                    policy.attrib.pop("remaining-quota-tokens-header-name", None)
                    policy.set("remaining-quota-header-name", "x-remaining-user-monthly-tokens")
                    with self.assertRaisesRegex(AssertionError, "unsupported"):
                        assert_token_limit_attributes(root)
                    policy.attrib.clear()
                    policy.attrib.update(original)

    def test_networking_profile_equality_is_unconditional(self):
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        step = workflow.split("      - name: Validate networking profile for every environment\n", 1)[1].split("      - name:", 1)[0]
        assert "if:" not in step
        command = '[[ "${APIM_NETWORKING_PROFILE}" == "${{ inputs.networking_profile }}" ]]'
        assert command in step
        assert workflow.count(command) == 1
        for configured in ("public", "private"):
            for selected in ("public", "private"):
                result = subprocess.run(["bash", "-c", command.replace("${{ inputs.networking_profile }}", selected)],
                                        env={**os.environ, "APIM_NETWORKING_PROFILE": configured}, capture_output=True)
                self.assertEqual(result.returncode == 0, configured == selected)

    def test_policy_and_deployment_invariants(self):
        policies = {name: (ROOT / f"apim/policies/{name}.xml").read_text()
                    for name in ("claude-base", "claude-messages", "claude-count-tokens", "claude-models")}
        base = policies["claude-base"]
        root = ET.fromstring(base)
        assert root.tag == "policies"
        for section in ("inbound", "backend", "outbound", "on-error"):
            assert root.find(section) is not None
        inbound = root.find("inbound")
        children = list(inbound)
        validation = inbound.find("validate-azure-ad-token")
        assert validation is not None
        assert validation.get("tenant-id") == "{{entra-tenant-id}}"
        assert validation.get("header-name") == "Authorization"
        assert validation.get("output-token-variable-name") == "validatedJwt"
        assert validation.get("failed-validation-httpcode") == "401"
        assert validation.findtext("./audiences/audience") == "{{expected-audience}}"
        for claim in ("oid", "tid"):
            assert validation.find(f"./required-claims/claim[@name='{claim}']") is not None
        assert validation.find("./required-claims/claim[@name='roles']") is None
        assert all(inbound.find(f"set-variable[@name='{name}']") is not None for name in (
            "callerObjectId", "callerTenantId", "callerAuthorized", "callerKey"))
        object_id = inbound.find("set-variable[@name='callerObjectId']")
        tenant_id = inbound.find("set-variable[@name='callerTenantId']")
        assert 'Claims.GetValueOrDefault("oid", "")' in object_id.get("value")
        assert 'Claims.GetValueOrDefault("tid", "")' in tenant_id.get("value")
        guard = inbound.find("choose")
        assert guard.find("when").get("condition") == '@(string.IsNullOrWhiteSpace((string)context.Variables["callerObjectId"]) || string.IsNullOrWhiteSpace((string)context.Variables["callerTenantId"]))'
        assert guard.find("when/return-response/set-status").get("code") == "401"
        assert guard.findtext("when/return-response/set-body") == "Invalid or missing Entra token."
        order = [validation, object_id, tenant_id, guard,
                 inbound.find("set-variable[@name='callerAuthorized']"),
                 inbound.find("set-variable[@name='callerKey']"), inbound.find("set-backend-service")]
        assert [children.index(node) for node in order] == sorted(children.index(node) for node in order)
        auth = inbound.find("set-variable[@name='callerAuthorized']").get("value")
        assert 'claims["roles"].Any(value => value == "{{required-app-role}}")' in auth
        assert 'var actor = version == "2.0" ? claims.GetValueOrDefault("azp", "") : version == "1.0" ? claims.GetValueOrDefault("appid", "") : "";' in auth
        assert 'var scopes = claims.GetValueOrDefault("scp", "").Split(\' \');' in auth
        assert 'scopes.Any(value => value == "{{claude-desktop-delegated-scope}}")' in auth
        assert 'return hasRole || ("{{claude-desktop-delegated-auth-enabled}}" == "true" && actor == "{{claude-desktop-client-id}}" && hasDesktopScope);' in auth
        assert inbound.find("./choose/when/return-response/set-status[@code='403']") is not None
        assert inbound.find("set-variable[@name='requestedModel']") is None
        assert inbound.find("set-variable[@name='modelCatalog']") is None
        assert len(inbound.findall("choose/when/return-response/set-status[@code='400']")) == 0
        assert all(f"{{{{{name}}}}}" not in base for name in ("opus-model", "sonnet-model", "haiku-model"))
        assert inbound.find("set-variable[@name='callerKey']").get("value") == '@((string)context.Variables["callerTenantId"] + ":" + (string)context.Variables["callerObjectId"])'
        deleted_headers = {node.get("name", "").lower() for node in inbound.findall("set-header") if node.get("exists-action") == "delete"}
        assert {"authorization", "x-api-key", "api-key", "ocp-apim-subscription-key"} <= deleted_headers
        deleted_query = {node.get("name", "").lower() for node in inbound.findall("set-query-parameter") if node.get("exists-action") == "delete"}
        assert {"subscription-key", "api-key", "access_token"} <= deleted_query
        delete_auth = inbound.find("set-header[@name='Authorization'][@exists-action='delete']")
        managed_identity = inbound.find("authentication-managed-identity")
        override_auth = inbound.find("set-header[@name='Authorization'][@exists-action='override']")
        assert children.index(delete_auth) < children.index(managed_identity) < children.index(override_auth)
        assert managed_identity.get("resource") == "https://ai.azure.com"
        assert inbound.find("set-backend-service").get("backend-id") == "foundry-backend"
        per_user = root.find("./backend/limit-concurrency")
        aggregate = per_user.find("limit-concurrency")
        assert "callerKey" in per_user.get("key")
        assert per_user.get("max-count") == "{{per-user-concurrent-stream-limit}}"
        assert aggregate.get("key") == "claude-foundry:aggregate"
        assert aggregate.get("max-count") == "{{aggregate-concurrent-stream-limit}}"
        assert aggregate.find("forward-request").get("buffer-response") == "false"
        assert "retry" not in "".join(policies.values()).lower()
        messages = ET.fromstring(policies["claude-messages"]).find("inbound")
        count_tokens = ET.fromstring(policies["claude-count-tokens"]).find("inbound")
        for policy in (messages, count_tokens):
            assert policy.find("base") is not None
            assert policy.find(".//quota-by-key") is None
            assert policy.find("rate-limit-by-key").get("counter-key") == '@("claude-foundry:rpm:" + (string)context.Variables["callerKey"])'
        assert count_tokens.find(".//llm-token-limit") is None
        assert messages.find("llm-token-limit") is None
        choose = messages.find("choose")
        assert [node.tag for node in choose] == ["when", "otherwise"]
        assert choose.find("when").get("condition") == '@(long.Parse("{{per-user-monthly-token-quota}}") > 0)'
        positive = choose.find("when/llm-token-limit")
        disabled = choose.find("otherwise/llm-token-limit")
        assert len(messages.findall(".//llm-token-limit")) == 2
        for policy in (positive, disabled):
            assert policy.get("counter-key") == '@("claude-foundry:tokens:" + (string)context.Variables["callerKey"])'
            assert policy.get("tokens-per-minute") == "{{per-user-token-limit}}"
            assert policy.get("estimate-prompt-tokens") == "true"
        assert positive.get("token-quota") == '@(long.Parse("{{per-user-monthly-token-quota}}"))'
        assert positive.get("token-quota-period") == "Monthly"
        assert positive.get("remaining-quota-tokens-header-name") == "x-remaining-user-monthly-tokens"
        assert "token-quota" not in disabled.attrib and "token-quota-period" not in disabled.attrib

        tofu = "\n".join(path.read_text() for path in (ROOT / "infra/tofu").glob("*.tf"))
        named_values = re.search(r"named_values\s*=\s*\{(.*?)\n  \}", tofu, re.S)
        assert named_values is not None
        managed = set(re.findall(r'"([a-z0-9-]+)"\s*=', named_values.group(1)))
        referenced = set(re.findall(r"\{\{([a-z0-9-]+)\}\}", "".join(policies.values())))
        assert referenced <= managed, f"unmanaged policy named values: {referenced - managed}"
        assert 'subscription_required = false' in tofu
        assert 'condition     = var.per_user_concurrent_stream_limit < var.aggregate_concurrent_stream_limit && var.aggregate_concurrent_stream_limit < 2048' in tofu
        assert 'condition     = var.default_capacity >= 1' in tofu
        assert 'var.default_capacity >= 2' not in tofu
        assert 'condition     = var.networking_profile != "private" || var.apim_sku_name == "PremiumV2"' in tofu
        assert 'condition     = !var.zone_redundant || var.apim_sku_name == "PremiumV2"' in tofu
        assert 'local_authentication_disabled = true' in tofu
        assert tofu.count('default     = "disabled"') == 2
        desktop = tofu.split('variable "enable_claude_desktop_delegated_auth"', 1)[1].split('variable ', 1)[0]
        assert 'default     = false' in desktop
        quota = tofu.split('variable "per_user_monthly_token_quota"', 1)[1].split('variable ', 1)[0]
        assert 'default     = 0' in quota and 'floor(var.per_user_monthly_token_quota)' in quota
        assert '9223372036854775807' in quota
        assert 'for_each = var.action_group_resource_id == "" ? [] : [var.action_group_resource_id]' in tofu
        breaker = tofu.split('resource "azurerm_api_management_backend" "foundry"', 1)[1].split('resource ', 1)[0]
        assert 'status_code_range {' in breaker and 'min = 500' in breaker and 'max = 599' in breaker
        assert "accept_retry_after" not in breaker.lower()
        assert "list" + "Secrets" not in tofu
        assert 'secret              = false' in tofu
        assert re.search(r'body_bytes\s*=\s*0', tofu)
        assert all(value == "0" for value in re.findall(r'body_bytes\s*=\s*(\d+)', tofu))
        api = tofu.split('resource "azurerm_api_management_api_policy" "claude"', 1)[1].split('resource ', 1)[0]
        assert 'azurerm_api_management_backend.foundry' in api
        assert 'azurerm_api_management_named_value.gateway' in api
        assert 'azurerm_role_assignment.foundry_user' in api
        operation = tofu.split('resource "azurerm_api_management_api_operation_policy" "claude"', 1)[1].split('resource ', 1)[0]
        assert 'depends_on          = [azurerm_api_management_api_policy.claude]' in operation
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        ha_workflow = (ROOT / ".github/workflows/ha-smoke.yml").read_text()
        assert "az deployment" not in workflow
        assert "tofu -chdir=infra/tofu plan" in workflow and "tofu -chdir=infra/tofu apply" in workflow
        assert "scripts/tofu/plan_summary.py" in workflow and 'cmp "${RUNNER_TEMP}/approved-plan/plan-summary.json"' in workflow
        assert "planned_change_sha256" in (ROOT / "scripts/tofu/plan_summary.py").read_text()
        assert "inputs.networking_profile == 'public'" in workflow
        assert "runs-on: [self-hosted" in ha_workflow
        assert "scripts/foundry_preflight.py" in workflow
        assert "secondary-foundry-preflight.json" in workflow
        assert workflow.count("allow-no-subscriptions: true") == 1
        assert "allow-no-subscriptions: true" in ha_workflow
        for caller in (workflow, ha_workflow):
            assert 'APIM_TENANT_ID: ${{ vars.ENTRA_TENANT_ID }}' in caller
        smoke_step = workflow.split("      - name: Post-deployment smoke test", 1)[1].split("      - name:", 1)[0]
        for role in ("OPUS", "SONNET", "HAIKU"):
            assert f"ANTHROPIC_DEFAULT_{role}_MODEL: ${{{{ inputs.deployment_mode == 'greenfield' && vars.CLAUDE_MODEL_DEPLOYMENT_NAME || vars.ANTHROPIC_DEFAULT_{role}_MODEL }}}}" in smoke_step
        assert 'PER_USER_MONTHLY_TOKEN_QUOTA: ${{ vars.PER_USER_MONTHLY_TOKEN_QUOTA }}' in workflow
        assert 'variable "deployment_mode"' in tofu
        assert 'resource "azurerm_resource_group" "greenfield"' in tofu
        assert 'resource "azapi_resource" "greenfield_foundry"' in tofu
        assert 'resource "azapi_resource" "greenfield_project"' in tofu
        assert 'resource "azapi_resource" "greenfield_claude"' in tofu
        assert 'resource "terraform_data" "deployment_mode"' in tofu
        assert 'triggers_replace = [var.deployment_mode]' in tofu
        assert 'depends_on = [azapi_resource.greenfield_project, azurerm_role_assignment.foundry_user["primary"]]' in tofu
        assert 'Microsoft.CognitiveServices/accounts@2026-05-01' in tofu
        assert 'Microsoft.CognitiveServices/accounts/projects@2026-05-01' in tofu
        assert 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' in tofu
        assert 'disableLocalAuth          = true' in tofu
        assert 'storedCompletionsDisabled = true' in tofu
        assert 'publicNetworkAccess       = "Enabled"' in tofu
        assert 'versionUpgradeOption = "NoAutoUpgrade"' in tofu
        assert 'provider "azuread"' not in tofu and 'provider "msgraph"' not in tofu
        assert 'deployment_mode:' in workflow
        assert 'accept_anthropic_marketplace_terms:' in workflow
        assert 'scripts/greenfield_foundry_preflight.py' in workflow
        assert "tofu -chdir=infra/tofu state show 'azurerm_resource_group.greenfield[0]'" in workflow
        assert '--allow-existing-resource-group' in workflow
        assert "jq '{primaryGatewayUrl:" in workflow
        assert 'for attempt in {1..6}; do' in workflow and 'sleep 30' in workflow
        assert workflow.count('scripts/foundry_preflight.py') >= 3
        assert 'os.walk(".", followlinks=False)' in (ROOT / "scripts/test/validate.sh").read_text()

    def test_models_get_inherits_authorization_and_returns_before_inference(self):
        root = ET.parse(ROOT / "apim/policies/claude-base.xml").getroot()
        inbound = root.find("inbound")
        children = list(inbound)
        branch = next(node for node in inbound.findall("choose") if node.find("when").get("condition") == '@(context.Operation.Id == "models" && context.Request.Method == "GET")')
        authorization = next(node for node in inbound.findall("choose") if node.find("when").get("condition") == '@(!(bool)context.Variables["callerAuthorized"])')
        order = [inbound.find("validate-azure-ad-token"), authorization,
                 inbound.find("set-variable[@name='callerKey']"), branch,
                 inbound.find("set-header[@name='Authorization'][@exists-action='delete']"),
                 inbound.find("set-backend-service"), inbound.find("authentication-managed-identity")]
        self.assertEqual([children.index(node) for node in order], sorted(children.index(node) for node in order))
        when = branch.find("when")
        self.assertEqual(list(when)[0].tag, "rate-limit-by-key")
        self.assertEqual(list(when)[-1].tag, "return-response")
        limit = when.find("rate-limit-by-key")
        self.assertEqual(limit.get("counter-key"), '@("claude-foundry:models:rpm:" + (string)context.Variables["callerKey"])')
        self.assertEqual(limit.get("calls"), "{{per-user-rate-limit}}")
        self.assertEqual(limit.get("renewal-period"), "60")
        self.assertNotIn("Request.Body", ET.tostring(branch, encoding="unicode"))
        for statement in ("llm-token-limit", "limit-concurrency", "set-backend-service"):
            self.assertIsNone(branch.find(f".//{statement}"))
        self.assertEqual(when.find("cache-lookup-value").get("caching-type"), "internal")
        miss = when.find("choose/when")
        self.assertIn('!context.Variables.ContainsKey("inventoryResult")', miss.get("condition"))
        admission = miss.find("rate-limit-by-key")
        self.assertEqual((admission.get("calls"), admission.get("renewal-period")), ("10", "10"))
        store = miss.find("cache-store-value")
        self.assertEqual((store.get("caching-type"), store.get("duration")), ("internal", "30"))
        self.assertEqual(len(root.findall(".//cache-lookup-value")), 1)
        self.assertEqual(len(root.findall(".//cache-store-value")), 1)
        self.assertIn("${inventory_pages}", ET.tostring(miss, encoding="unicode"))
        error = root.find("on-error/choose/when")
        self.assertIn('context.Variables.ContainsKey("inventoryActive")', error.get("condition"))
        self.assertEqual(error.find("return-response/set-status").get("code"), "503")
        self.assertEqual([node.tag for node in root.find("on-error")], ["choose", "base"])
        models = ET.parse(ROOT / "apim/policies/claude-models.xml").getroot()
        for section in ("inbound", "backend", "outbound", "on-error"):
            self.assertEqual([node.tag for node in models.find(section)], ["base"])
        health = ET.parse(ROOT / "infra/tofu/policies/health.xml").getroot()
        self.assertIsNone(health.find("inbound/base"))
        self.assertEqual(health.findtext("inbound/return-response/set-body"), "healthy")
        tofu = (ROOT / "infra/tofu/main.tf").read_text()
        operation = tofu.split("    models = {", 1)[1].split("    }", 1)[0]
        self.assertIn('method       = "GET"', operation)
        self.assertIn('url_template = "/v1/models"', operation)
        self.assertIn('apim/policies/claude-models.xml', operation)
        named_values = tofu.split("  named_values = {", 1)[1].split("\n  }", 1)[0]
        self.assertNotIn("model_catalog", named_values)

    def test_discovery_workflow_is_opt_in_read_only_and_artifact_only(self):
        workflow = (ROOT / ".github/workflows/sync-models.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertRegex(workflow, r"cron: '[0-9]+ [0-9]+ \* \* \*'")
        self.assertIn("if: vars.MODEL_DISCOVERY_ENABLED == 'true'", workflow)
        self.assertIn("environment: model-discovery", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        for secret in ("AZURE_MODEL_DISCOVERY_CLIENT_ID", "AZURE_MODEL_DISCOVERY_TENANT_ID"):
            self.assertIn(f"${{{{ secrets.{secret} }}}}", workflow)
        for forbidden in ("secrets.AZURE_CLIENT_ID", "secrets.AZURE_TENANT_ID", "tofu ", "az deployment", "az rest", "git push", "create-pull-request", "repository_dispatch", "gh workflow", "workflow_run:"):
            self.assertNotIn(forbidden, workflow)
        deploy = (ROOT / ".github/workflows/deploy.yml").read_text()
        actions = re.findall(r"uses: ([^\s]+)", workflow)
        for action in actions:
            self.assertRegex(action, r"@[0-9a-f]{40}$")
            self.assertIn(action, deploy)
        self.assertIn("scripts/sync_claude_models.py", workflow)
        self.assertIn('--report-file "${RUNNER_TEMP}/model-discovery/report.json"', workflow)
        self.assertIn('git show "${GITHUB_SHA}:${MODEL_CATALOG_FILE}"', workflow)
        self.assertIn("ref: ${{ github.sha }}", workflow)

    def test_deploy_freezes_reviewed_catalog_from_commit_never_rediscovers_at_apply(self):
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        self.assertIn("MODEL_CATALOG_FILE: ${{ vars.MODEL_CATALOG_FILE }}", workflow)
        frozen = 'git show "${GITHUB_SHA}:${MODEL_CATALOG_FILE}" > "${RUNNER_TEMP}/model-catalog.json"'
        self.assertEqual(workflow.count(frozen), 2)
        self.assertEqual(workflow.count('export MODEL_CATALOG_FILE="${RUNNER_TEMP}/model-catalog.json"'), 2)
        self.assertNotIn("sync_claude_models.py", workflow)
        self.assertIn("${{ runner.temp }}/model-catalog.json", workflow)
        self.assertIn('"model_catalog_sha256": catalog_sha256', workflow)
        self.assertIn('assert context["model_catalog_sha256"] ==', workflow)
        self.assertIn('assert context["inputs_sha256"] == digest', workflow)
        for job in ("  plan:", "  deploy:"):
            section = workflow.split(job, 1)[1].split("\n  smoke:", 1)[0]
            self.assertLess(section.index("ref: ${{ github.sha }}"), section.index(frozen))
            self.assertLess(section.index(frozen), section.index("python3 scripts/tofu/generate_tfvars.py"))

    def test_workflow_approval_hashes_reject_catalog_or_embedded_input_changes(self):
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        plan_code = textwrap.dedent(workflow.split("python3 - <<'PY' >", 1)[1].split("\n", 1)[1].split("\n          PY", 1)[0])
        apply_code = textwrap.dedent(workflow.split("python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "infra/tofu").mkdir(parents=True)
            (root / "infra/tofu/.terraform.lock.hcl").write_text("synthetic lockfile")
            (root / "approved-plan").mkdir()
            catalog_path = root / "catalog.json"
            catalog_bytes = (ROOT / "scripts/test/fixtures/model-discovery/catalog.json").read_bytes()
            catalog_path.write_bytes(catalog_bytes)
            inputs_path = root / "inputs.tfvars.json"
            inputs_bytes = json.dumps({"model_catalog": json.loads(catalog_bytes)}).encode()
            inputs_path.write_bytes(inputs_bytes)
            env = {**os.environ, "RUNNER_TEMP": directory, "MODEL_CATALOG_FILE": str(catalog_path),
                   "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "1", "DEPLOYMENT_MODE": "existing",
                   "ACCEPT_ANTHROPIC_MARKETPLACE_TERMS": "false", "ENVIRONMENT_PROFILE": "poc",
                   "ARM_SUBSCRIPTION_ID": "synthetic", "TOFU_STATE_SUBSCRIPTION_ID": "synthetic",
                   "TOFU_STATE_RG": "synthetic", "TOFU_STATE_STORAGE_ACCOUNT": "synthetic",
                   "TOFU_STATE_CONTAINER": "synthetic", "TOFU_STATE_KEY": "synthetic"}

            def run(code):
                return subprocess.run([sys.executable, "-B", "-c", code], cwd=root, env=env, capture_output=True, text=True, timeout=30)

            plan = run(plan_code)
            self.assertEqual(plan.returncode, 0, plan.stderr)
            (root / "approved-plan/run-context.json").write_text(plan.stdout)
            self.assertEqual(run(apply_code).returncode, 0)
            for path in (catalog_path, inputs_path):
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                self.assertNotEqual(run(apply_code).returncode, 0)
                path.write_bytes(original)


class MarkdownLinkScanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.root.mkdir()
        (self.root / "README.md").write_text("[valid](README.md)\n")

    def scan(self):
        scanner = (ROOT / "scripts/test/validate.sh").read_text().split("python3 - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
        # Fail even if a walker enters an excluded directory but later skips its files.
        guard = '''from pathlib import Path
import sys
boundary = Path.cwd()
def deny_traversal(event, args):
    if event in {"open", "os.scandir"} and isinstance(args[0], str):
        path = Path(args[0]).absolute()
        if path.is_relative_to(boundary):
            assert not set(path.relative_to(boundary).parts) & {
                "claudecodepoc-hard", ".git", ".terraform", "node_modules",
                "cache", ".cache", "__pycache__", ".pytest_cache"}, "visited excluded directory"
            assert not path.is_symlink(), "followed symlink"
sys.addaudithook(deny_traversal)
'''
        return subprocess.run([sys.executable, "-B", "-c", guard + scanner], cwd=self.root,
                              capture_output=True, text=True, timeout=10)

    def test_prunes_retained_child_and_generated_directories_before_walking(self):
        for name in ("claudecodepoc-hard", ".git", ".terraform", "node_modules",
                     "cache", ".cache", "__pycache__", ".pytest_cache"):
            directory = self.root / name / "nested"
            directory.mkdir(parents=True)
            (directory / "broken.md").write_text("[broken](missing.md)\n")
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_own_broken_link_fails_including_azure_source(self):
        for name in ("docs", ".azure"):
            with self.subTest(directory=name):
                directory = self.root / name
                directory.mkdir()
                page = directory / "broken.md"
                page.write_text("[broken](missing.md)\n")
                result = self.scan()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"broken Markdown link: {name}/broken.md -> missing.md", result.stderr)
                page.unlink()

    def test_does_not_follow_directory_or_markdown_symlinks(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / "broken.md").write_text("[broken](missing.md)\n")
        (self.root / "linked-directory").symlink_to(outside, target_is_directory=True)
        (self.root / "linked.md").symlink_to(outside / "broken.md")
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stderr)
