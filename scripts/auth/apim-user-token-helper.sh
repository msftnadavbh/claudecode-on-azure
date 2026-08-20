#!/usr/bin/env bash
set -euo pipefail
umask 077

if ! command -v az >/dev/null 2>&1; then
  echo "az is required" >&2
  exit 1
fi

APIM_AUDIENCE="${APIM_AUDIENCE:-}"
if [[ -z "${APIM_AUDIENCE}" ]]; then
  echo "APIM_AUDIENCE must be set (for example api://example-claude-gateway)" >&2
  exit 1
fi

token="$(az account get-access-token --resource "${APIM_AUDIENCE}" --query accessToken --output tsv)"
if [[ -z "${token}" || "${token}" == "null" ]]; then
  echo "Unable to acquire access token" >&2
  exit 1
fi
printf '%s\n' "${token}"
