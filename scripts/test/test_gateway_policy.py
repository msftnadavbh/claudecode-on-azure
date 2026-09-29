"""Offline structural evidence only; live Entra/APIM behavior still needs validation."""
from pathlib import Path
import os
import re
import subprocess
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
                    for name in ("claude-base", "claude-messages", "claude-count-tokens")}
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
        model = inbound.find("set-variable[@name='requestedModel']")
        assert model is not None and 'As<JObject>(preserveContent: true)' in model.get("value", "")
        assert len(inbound.findall("choose/when/return-response/set-status[@code='400']")) == 1
        assert all(f"{{{{{name}}}}}" in base for name in ("opus-model", "sonnet-model", "haiku-model"))
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
        assert 'from pathlib import Path\nimport re\n\nfor page in Path(".").glob("**/*.md")' in (ROOT / "scripts/test/validate.sh").read_text()
