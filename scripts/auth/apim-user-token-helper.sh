#!/usr/bin/env bash
set -euo pipefail
umask 077

if ! command -v az >/dev/null 2>&1; then
  echo "az is required" >&2
  exit 1
fi

APIM_AUDIENCE="${APIM_AUDIENCE:-}"
APIM_TENANT_ID="${APIM_TENANT_ID:-}"
if [[ -z "${APIM_AUDIENCE//[[:space:]]/}" || -z "${APIM_TENANT_ID//[[:space:]]/}" ]]; then
  echo "APIM_AUDIENCE and APIM_TENANT_ID must be set" >&2
  exit 1
fi

# Keep a sentinel so command substitution cannot hide extra trailing newlines.
if ! token="$(az account get-access-token --tenant "${APIM_TENANT_ID}" --resource "${APIM_AUDIENCE}" --query accessToken --output tsv </dev/null 2>/dev/null && printf '.')"; then
  echo "Unable to acquire access token" >&2
  exit 1
fi
token="${token%.}"
token="${token%$'\n'}"
token="${token%$'\r'}"
if [[ -z "${token}" || "${token}" == "null" || "${token}" == *[[:space:][:cntrl:]]* ]]; then
  echo "Unable to acquire access token" >&2
  exit 1
fi
printf '%s\n' "${token}"
