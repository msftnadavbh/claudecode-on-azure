#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-prod}"
APIM_BASE_URL="${APIM_BASE_URL:-https://apim-claude-prod.azure-api.net/claude}"

if [[ "${PROFILE}" != "prod" && "${PROFILE}" != "poc" ]]; then
  echo "Usage: $0 [prod|poc]" >&2
  exit 1
fi

cat <<OUT
export CLAUDE_CODE_USE_FOUNDRY=1
export ANTHROPIC_FOUNDRY_BASE_URL=${APIM_BASE_URL}
export APIM_AUDIENCE=${APIM_AUDIENCE:-api://example-claude-gateway}
export CLAUDE_CODE_API_KEY_HELPER_TTL_MS=${CLAUDE_CODE_API_KEY_HELPER_TTL_MS:-300000}

# Claude Code managed settings:
# apiKeyHelper=$(cd "$(dirname "$0")/../.." && pwd)/scripts/auth/apim-user-token-helper.sh
OUT

if [[ "${PROFILE}" == "poc" ]]; then
  cat <<OUT
# PoC profile intentionally uses tiny APIM policy limits.
OUT
fi
