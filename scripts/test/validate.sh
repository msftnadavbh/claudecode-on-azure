#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${repo_root}"

while IFS= read -r file; do
  bash -n "${file}"
  shellcheck "${file}"
done < <(find scripts -type f -name '*.sh' | sort)

while IFS= read -r file; do
  python3 -m py_compile "${file}"
done < <(find scripts -type f -name '*.py' | sort)
python3 -m unittest discover -s scripts/test -p 'test_*.py'
python3 migration/tofu/test_generate_import_manifest.py

python3 - <<'PY'
from pathlib import Path
import re
import xml.etree.ElementTree as ET

policies = {
    name: Path(f"apim/policies/{name}.xml").read_text()
    for name in ("claude-base", "claude-messages", "claude-count-tokens")
}
base = policies["claude-base"]
root = ET.fromstring(base)
assert root.tag == "policies"
for section in ("inbound", "backend", "outbound", "on-error"):
    assert root.find(section) is not None, f"missing policy section: {section}"

inbound = root.find("inbound")
children = list(inbound)
validation = inbound.find("validate-azure-ad-token")
assert validation is not None
assert validation.get("tenant-id") == "{{entra-tenant-id}}"
assert validation.get("header-name") == "Authorization"
assert validation.get("output-token-variable-name") == "validatedJwt"
assert validation.findtext("./audiences/audience") == "{{expected-audience}}"
for claim in ("oid", "tid"):
    assert validation.find(f"./required-claims/claim[@name='{claim}']") is not None
assert validation.find("./required-claims/claim[@name='roles']") is None
assert all(inbound.find(f"set-variable[@name='{name}']") is not None for name in (
    "callerObjectId", "callerTenantId", "callerAuthorized", "callerKey",
))
for claim in ("roles", "azp", "appid", "scp"):
    assert f"&quot;{claim}&quot;" in base
assert 'actor == &quot;{{claude-desktop-client-id}}&quot;' in base
assert 'value == &quot;{{claude-desktop-delegated-scope}}&quot;' in base
assert '&quot;{{claude-desktop-delegated-auth-enabled}}&quot; == &quot;true&quot;' in base
assert inbound.find("./choose/when/return-response/set-status[@code='403']") is not None
model = inbound.find("set-variable[@name='requestedModel']")
assert model is not None and 'As<JObject>(preserveContent: true)' in model.get("value", "")
model_rejection = inbound.findall("choose/when/return-response/set-status[@code='400']")
assert len(model_rejection) == 1
assert all(f"{{{{{name}}}}}" in base for name in ("opus-model", "sonnet-model", "haiku-model"))

deleted_headers = {
    node.get("name", "").lower()
    for node in inbound.findall("set-header")
    if node.get("exists-action") == "delete"
}
assert {"authorization", "x-api-key", "api-key", "ocp-apim-subscription-key"} <= deleted_headers
deleted_query = {
    node.get("name", "").lower()
    for node in inbound.findall("set-query-parameter")
    if node.get("exists-action") == "delete"
}
assert {"subscription-key", "api-key", "access_token"} <= deleted_query

delete_auth = inbound.find("set-header[@name='Authorization'][@exists-action='delete']")
managed_identity = inbound.find("authentication-managed-identity")
override_auth = inbound.find("set-header[@name='Authorization'][@exists-action='override']")
assert children.index(delete_auth) < children.index(managed_identity) < children.index(override_auth)
assert managed_identity.get("resource") == "https://ai.azure.com"
assert inbound.find("set-backend-service").get("backend-id") == "foundry-backend"
per_user = root.find("./backend/limit-concurrency")
aggregate = per_user.find("limit-concurrency")
forward = aggregate.find("forward-request")
assert "callerKey" in per_user.get("key")
assert per_user.get("max-count") == "{{per-user-concurrent-stream-limit}}"
assert aggregate.get("key") == "claude-foundry:aggregate"
assert aggregate.get("max-count") == "{{aggregate-concurrent-stream-limit}}"
assert forward.get("buffer-response") == "false"
assert "retry" not in "".join(policies.values()).lower()

messages = ET.fromstring(policies["claude-messages"]).find("inbound")
count_tokens = ET.fromstring(policies["claude-count-tokens"]).find("inbound")
assert messages.find("rate-limit-by-key") is not None
assert messages.find("llm-token-limit") is not None
assert count_tokens.find("rate-limit-by-key") is not None
assert count_tokens.find("llm-token-limit") is None
assert all(policy.find("quota-by-key") is None for policy in (messages, count_tokens))
assert messages.find("base") is not None and count_tokens.find("base") is not None

tofu = "\n".join(path.read_text() for path in Path("infra/tofu").glob("*.tf"))
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
assert 'for_each = var.action_group_resource_id == "" ? [] : [var.action_group_resource_id]' in tofu
breaker = tofu.split('resource "azurerm_api_management_backend" "foundry"', 1)[1].split('resource ', 1)[0]
assert 'status_code_range {' in breaker and 'min = 500' in breaker and 'max = 599' in breaker
assert "accept_retry_after" not in breaker.lower()
assert "listSecrets" not in tofu
assert 'secret              = false' in tofu
assert re.search(r'body_bytes\s*=\s*0', tofu)
assert all(value == "0" for value in re.findall(r'body_bytes\s*=\s*(\d+)', tofu))

workflow = Path(".github/workflows/deploy.yml").read_text()
ha_workflow = Path(".github/workflows/ha-smoke.yml").read_text()
assert "az deployment" not in workflow
assert "tofu -chdir=infra/tofu plan" in workflow and "tofu -chdir=infra/tofu apply" in workflow
assert "scripts/tofu/plan_summary.py" in workflow and "cmp \"${RUNNER_TEMP}/approved-plan/plan-summary.json\"" in workflow
assert "planned_change_sha256" in Path("scripts/tofu/plan_summary.py").read_text()
assert "inputs.networking_profile == 'public'" in workflow
assert "runs-on: [self-hosted" in ha_workflow
assert "scripts/foundry_preflight.py" in workflow
assert "secondary-foundry-preflight.json" in workflow
assert workflow.count("allow-no-subscriptions: true") == 1
assert "allow-no-subscriptions: true" in ha_workflow
assert 'azurerm_api_management_backend.foundry' in tofu.split('resource "azurerm_api_management_api_policy" "claude"', 1)[1].split('resource ', 1)[0]
PY

tofu -chdir=infra/tofu fmt -check
tofu -chdir=infra/tofu init -input=false -backend=false -lockfile=readonly
tofu -chdir=infra/tofu validate

if grep -R -n -E '(listSecrets|ANTHROPIC_(API_KEY|AUTH_TOKEN)=|Ocp-Apim-Subscription-Key:|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
  README.md CLAUDE.md docs infra apim scripts migration .github --exclude='validate.sh' --exclude-dir='.terraform'; then
  echo "Forbidden production credential pattern found" >&2
  exit 1
fi

echo "Validation checks passed."
