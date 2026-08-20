#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-prod}"

case "${PROFILE}" in
  prod)
    default_apim_base_url="https://apim-claude-prod.azure-api.net/claude"
    ;;
  poc)
    default_apim_base_url="https://apim-claude-poc.azure-api.net/claude"
    ;;
  *)
    echo "Usage: $0 [prod|poc]" >&2
    exit 1
    ;;
esac

apim_base_url="${APIM_BASE_URL:-${default_apim_base_url}}"
apim_audience="${APIM_AUDIENCE:-api://example-claude-gateway}"
helper_ttl_ms="${CLAUDE_CODE_API_KEY_HELPER_TTL_MS:-300000}"

printf 'export CLAUDE_CODE_USE_FOUNDRY=1\n'
printf 'export ANTHROPIC_FOUNDRY_BASE_URL=%q\n' "${apim_base_url}"
printf 'export APIM_AUDIENCE=%q\n' "${apim_audience}"
printf 'export CLAUDE_CODE_API_KEY_HELPER_TTL_MS=%q\n' "${helper_ttl_ms}"
cat <<OUT
# Claude Code managed settings:
# apiKeyHelper=$(cd "$(dirname "$0")/../.." && pwd)/scripts/auth/apim-user-token-helper.sh
OUT

if [[ "${PROFILE}" == "poc" ]]; then
  cat <<OUT
# PoC profile intentionally uses tiny APIM policy limits.
OUT
fi
