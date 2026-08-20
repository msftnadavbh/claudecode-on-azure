#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${repo_root}"

# Shell lint (syntax).
while IFS= read -r f; do
  bash -n "$f"
done < <(find scripts -type f -name '*.sh' | sort)

if command -v shellcheck >/dev/null 2>&1; then
  while IFS= read -r f; do
    shellcheck "$f"
  done < <(find scripts -type f -name '*.sh' | sort)
fi

# Python syntax checks.
while IFS= read -r f; do
  python3 -m py_compile "$f"
done < <(find scripts -type f -name '*.py' | sort)

# Parse the APIM policy and verify security-sensitive policy ordering.
python3 - <<'PY'
import xml.etree.ElementTree as ET

root = ET.parse("apim/policies/claude-messages.xml").getroot()
assert root.tag == "policies"
for section in ("inbound", "backend", "outbound", "on-error"):
    assert root.find(section) is not None, f"missing policy section: {section}"

inbound = root.find("inbound")
children = list(inbound)
token_validation = inbound.find("validate-azure-ad-token")
assert token_validation is not None
assert token_validation.find("./required-claims/claim[@name='oid']") is not None
role = token_validation.find("./required-claims/claim[@name='roles']/value")
assert role is not None and role.text == "{{required-app-role}}"
assert children.index(token_validation) < children.index(inbound.find("rate-limit-by-key"))
assert inbound.find("set-header[@name='Authorization'][@exists-action='delete']") is not None
assert inbound.find("authentication-managed-identity") is not None
assert inbound.find("llm-token-limit") is not None
assert root.find("./backend/forward-request").get("buffer-response") == "false"
PY

# Compile the entrypoint/module graph and both parameter profiles.
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

AZURE_LOCATION=test \
APIM_NAME=test-apim \
APIM_PUBLISHER_EMAIL=test@example.com \
APIM_PUBLISHER_NAME=Test \
FOUNDRY_BASE_URL=https://example.services.ai.azure.com/anthropic \
APIM_EXPECTED_AUDIENCE=api://test \
APIM_REQUIRED_APP_ROLE=ClaudeCode.User \
PER_USER_RATE_LIMIT=1 \
PER_USER_HOURLY_QUOTA=1 \
PER_USER_TOKEN_LIMIT=1 \
  "${build_prod_params[@]}"

echo "Validation checks passed."
