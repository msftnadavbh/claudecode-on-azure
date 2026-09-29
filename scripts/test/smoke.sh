#!/usr/bin/env bash
set -euo pipefail

: "${APIM_BASE_URL:?Set APIM_BASE_URL, for example https://gateway.example/claude}"
: "${APIM_TOKEN_HELPER:?Set APIM_TOKEN_HELPER to the approved user token helper}"
: "${ANTHROPIC_DEFAULT_OPUS_MODEL:?Set the pinned Opus deployment name}"
: "${ANTHROPIC_DEFAULT_SONNET_MODEL:?Set the pinned Sonnet deployment name}"
: "${ANTHROPIC_DEFAULT_HAIKU_MODEL:?Set the pinned Haiku deployment name}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "${script_dir}/endpoint_smoke_matrix.py" \
  --endpoint "primary=${APIM_BASE_URL}" \
  --token-helper "${APIM_TOKEN_HELPER}" \
  --model "opus=${ANTHROPIC_DEFAULT_OPUS_MODEL}" \
  --model "sonnet=${ANTHROPIC_DEFAULT_SONNET_MODEL}" \
  --model "haiku=${ANTHROPIC_DEFAULT_HAIKU_MODEL}"
