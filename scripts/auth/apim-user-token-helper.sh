#!/usr/bin/env bash
set -euo pipefail
umask 077

for command_name in az jq; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "${command_name} is required" >&2
    exit 1
  fi
done

APIM_AUDIENCE="${APIM_AUDIENCE:-}"
if [[ -z "${APIM_AUDIENCE}" ]]; then
  echo "APIM_AUDIENCE must be set (for example api://example-claude-gateway)" >&2
  exit 1
fi

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/claude-code"
CACHE_FILE="${CACHE_DIR}/apim-token.json"
TTL_MS="${CLAUDE_CODE_API_KEY_HELPER_TTL_MS:-300000}"
if [[ ! "${TTL_MS}" =~ ^[0-9]+$ ]]; then
  echo "CLAUDE_CODE_API_KEY_HELPER_TTL_MS must be a non-negative integer" >&2
  exit 1
fi

mkdir -p "${CACHE_DIR}"
chmod 700 "${CACHE_DIR}"

now_epoch="$(date +%s)"
if [[ -f "${CACHE_FILE}" ]]; then
  chmod 600 "${CACHE_FILE}"
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

if [[ -z "${new_token}" || "${new_token}" == "null" ]]; then
  echo "Unable to acquire access token" >&2
  exit 1
fi

expires_epoch="$(printf '%s' "${raw_json}" | jq -r '.expires_on // 0')"
if [[ ! "${expires_epoch}" =~ ^[0-9]+$ ]]; then
  expires_epoch=0
fi
if (( expires_epoch == 0 )) && command -v python3 >/dev/null 2>&1; then
  expires_on="$(printf '%s' "${raw_json}" | jq -r '.expiresOn // empty')"
  if [[ -n "${expires_on}" ]]; then
    expires_epoch="$(
      python3 - "${expires_on}" <<'PY' || echo 0
from datetime import datetime
import sys

value = sys.argv[1].replace("Z", "+00:00")
expires = datetime.fromisoformat(value)
if expires.tzinfo is None:
    expires = expires.astimezone()
print(int(expires.timestamp()))
PY
    )"
  fi
fi
temp_file="$(mktemp "${CACHE_FILE}.XXXXXX")"
trap 'rm -f "${temp_file}"' EXIT
jq -n --arg token "${new_token}" --argjson expires_epoch "${expires_epoch}" '{token: $token, expires_epoch: $expires_epoch}' > "${temp_file}"
chmod 600 "${temp_file}"
mv "${temp_file}" "${CACHE_FILE}"
trap - EXIT
printf '%s\n' "${new_token}"
