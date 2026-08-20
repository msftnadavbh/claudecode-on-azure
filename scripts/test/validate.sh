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

python3 - <<'PY'
from pathlib import Path
import re
import xml.etree.ElementTree as ET

policy_path = Path("apim/policies/claude-messages.xml")
policy_text = policy_path.read_text()
root = ET.fromstring(policy_text)
assert root.tag == "policies"
for section in ("inbound", "backend", "outbound", "on-error"):
    assert root.find(section) is not None, f"missing policy section: {section}"

inbound = root.find("inbound")
children = list(inbound)
validation = inbound.find("validate-azure-ad-token")
assert validation is not None
assert validation.get("tenant-id") == "{{entra-tenant-id}}"
assert validation.get("header-name") == "x-api-key"
for claim in ("oid", "tid", "roles"):
    assert validation.find(f"./required-claims/claim[@name='{claim}']") is not None
assert children.index(validation) < children.index(inbound.find("rate-limit-by-key"))

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
assert {"subscription-key", "api-key"} <= deleted_query

delete_auth = inbound.find("set-header[@name='Authorization'][@exists-action='delete']")
managed_identity = inbound.find("authentication-managed-identity")
override_auth = inbound.find("set-header[@name='Authorization'][@exists-action='override']")
assert children.index(delete_auth) < children.index(managed_identity) < children.index(override_auth)
assert managed_identity.get("resource") == "https://cognitiveservices.azure.com"
assert inbound.find("set-backend-service").get("backend-id") == "foundry-backend"
assert inbound.find("llm-token-limit") is not None
assert inbound.find("set-header[@name='x-apim-caller-key']") is None
assert root.find("./backend/forward-request").get("buffer-response") == "false"

module_text = Path("infra/modules/apim.bicep").read_text()
managed_named_values = set(re.findall(r"'([a-z0-9-]+)'\s*:", re.search(
    r"var namedValues = \{(.*?)\n\}", module_text, re.S
).group(1)))
referenced_named_values = set(re.findall(r"\{\{([a-z0-9-]+)\}\}", policy_text))
assert referenced_named_values <= managed_named_values, (
    f"unmanaged policy named values: {referenced_named_values - managed_named_values}"
)
for route in ("/v1/messages", "/v1/messages/count_tokens"):
    assert route in module_text
assert "subscriptionRequired: false" in module_text
assert "circuitBreaker:" in module_text and "acceptRetryAfter: true" in module_text
assert "body:" in module_text and module_text.count("bytes: 0") >= 4

main_text = Path("infra/main.bicep").read_text()
prod_text = Path("infra/params/prod.bicepparam").read_text()
for name in (
    "entraTenantId", "opusDeploymentName", "sonnetDeploymentName",
    "haikuDeploymentName", "minimumCapacity", "defaultCapacity",
    "maximumCapacity", "deploySecondary", "networkingProfile",
):
    assert f"param {name}" in main_text or f"param {name}" in prod_text
assert "defaultCapacity = 1" not in prod_text
assert "param apimSkuName = 'BasicV2'" in Path("infra/params/poc.bicepparam").read_text()

workflow = Path(".github/workflows/deploy.yml").read_text()
assert "az deployment group create" in workflow
assert "scripts/test/smoke.sh" in workflow
PY

build_dir="$(mktemp -d)"
trap 'rm -rf "${build_dir}"' EXIT

if command -v bicep >/dev/null 2>&1; then
  bicep build infra/main.bicep --outfile "${build_dir}/main.json"
  bicep build-params infra/params/poc.bicepparam --outfile "${build_dir}/poc.parameters.json"
  build_prod_params=(bicep build-params infra/params/prod.bicepparam --outfile "${build_dir}/prod.parameters.json")
elif command -v az >/dev/null 2>&1; then
  az bicep build --file infra/main.bicep --outfile "${build_dir}/main.json"
  az bicep build-params --file infra/params/poc.bicepparam --outfile "${build_dir}/poc.parameters.json"
  build_prod_params=(az bicep build-params --file infra/params/prod.bicepparam --outfile "${build_dir}/prod.parameters.json")
else
  echo "Bicep CLI or Azure CLI is required" >&2
  exit 1
fi

AZURE_LOCATION=eastus \
AZURE_SECONDARY_LOCATION=westus2 \
APIM_NAME=test-primary \
APIM_SECONDARY_NAME=test-secondary \
APIM_PUBLISHER_EMAIL=test@example.com \
APIM_PUBLISHER_NAME=Test \
ENTRA_TENANT_ID=11111111-1111-1111-1111-111111111111 \
FOUNDRY_BASE_URL=https://primary.services.ai.azure.com/anthropic \
FOUNDRY_SECONDARY_BASE_URL=https://secondary.services.ai.azure.com/anthropic \
FOUNDRY_SUBSCRIPTION_ID=22222222-2222-2222-2222-222222222222 \
FOUNDRY_RESOURCE_GROUP=test-foundry-primary \
FOUNDRY_ACCOUNT_NAME=test-foundry-primary \
FOUNDRY_SECONDARY_RESOURCE_GROUP=test-foundry-secondary \
FOUNDRY_SECONDARY_ACCOUNT_NAME=test-foundry-secondary \
APIM_EXPECTED_AUDIENCE=api://test \
APIM_REQUIRED_APP_ROLE=ClaudeCode.User \
ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-pinned \
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-pinned \
ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-pinned \
PER_USER_RATE_LIMIT=100 \
PER_USER_HOURLY_QUOTA=500 \
PER_USER_TOKEN_LIMIT=50000 \
APIM_MIN_CAPACITY=2 \
APIM_DEFAULT_CAPACITY=2 \
APIM_MAX_CAPACITY=10 \
APIM_SCALE_OUT_CPU_THRESHOLD=70 \
APIM_SCALE_IN_CPU_THRESHOLD=30 \
APIM_NETWORKING_PROFILE=public \
APIM_SUBNET_RESOURCE_ID='' \
APIM_PRIVATE_ENDPOINT_SUBNET_RESOURCE_ID='' \
APIM_SECONDARY_SUBNET_RESOURCE_ID='' \
APIM_SECONDARY_PRIVATE_ENDPOINT_SUBNET_RESOURCE_ID='' \
APIM_PRIVATE_DNS_ZONE_RESOURCE_ID='' \
ACTION_GROUP_RESOURCE_ID='' \
TRAFFIC_MANAGER_NAME=test-claude-failover \
  "${build_prod_params[@]}"

if grep -R -n -E '(listSecrets|ANTHROPIC_(API_KEY|AUTH_TOKEN)=|Ocp-Apim-Subscription-Key:)' \
  README.md CLAUDE.md docs infra apim scripts .github --exclude='validate.sh'; then
  echo "Forbidden production credential pattern found" >&2
  exit 1
fi

echo "Validation checks passed."
