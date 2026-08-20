#!/usr/bin/env bash
set -euo pipefail

if ! command -v az >/dev/null 2>&1; then
  echo "az CLI is required" >&2
  exit 1
fi

APIM_AUDIENCE="${APIM_AUDIENCE:-}"
if [[ -z "${APIM_AUDIENCE}" ]]; then
  echo "APIM_AUDIENCE must be set (for example api://example-claude-gateway)" >&2
  exit 1
fi

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/claude-code"
CACHE_FILE="${CACHE_DIR}/apim-token.json"
TTL_MS="${CLAUDE_CODE_API_KEY_HELPER_TTL_MS:-300000}"
mkdir -p "${CACHE_DIR}"

now_epoch="$(date +%s)"
if [[ -f "${CACHE_FILE}" ]]; then
  expires_epoch="$(jq -r '.expires_epoch // 0' "${CACHE_FILE}" 2>/dev/null || echo 0)"
  token="$(jq -r '.token // empty' "${CACHE_FILE}" 2>/dev/null || true)"
  if [[ -n "${token}" ]]; then
    buffer_secs="$(( TTL_MS / 1000 ))"
    if (( expires_epoch - now_epoch > buffer_secs )); then
      printf '%s\n' "${token}"
      exit 0
    fi
  fi
fi

raw_json="$(az account get-access-token --resource "${APIM_AUDIENCE}" --output json)"
new_token="$(printf '%s' "${raw_json}" | jq -r '.accessToken')"
expires_on="$(printf '%s' "${raw_json}" | jq -r '.expiresOn')"

if [[ -z "${new_token}" || "${new_token}" == "null" ]]; then
  echo "Unable to acquire access token" >&2
  exit 1
fi

expires_epoch="$(date -d "${expires_on}" +%s 2>/dev/null || echo 0)"
jq -n --arg token "${new_token}" --argjson expires_epoch "${expires_epoch}" '{token: $token, expires_epoch: $expires_epoch}' > "${CACHE_FILE}"
printf '%s\n' "${new_token}"
