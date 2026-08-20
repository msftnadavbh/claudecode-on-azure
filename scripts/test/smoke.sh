#!/usr/bin/env bash
set -euo pipefail

: "${APIM_BASE_URL:?Set APIM_BASE_URL, for example https://gateway.example/claude}"
: "${APIM_TOKEN_HELPER:?Set APIM_TOKEN_HELPER to the approved user token helper}"
: "${ANTHROPIC_DEFAULT_SONNET_MODEL:?Set the pinned Sonnet deployment name}"

credential="$("${APIM_TOKEN_HELPER}")"
common_headers=(-H "x-api-key: ${credential}" -H 'content-type: application/json' -H 'anthropic-version: 2023-06-01')
count_body="$(printf '{"model":"%s","messages":[{"role":"user","content":"Reply only OK"}]}' "${ANTHROPIC_DEFAULT_SONNET_MODEL}")"
stream_body="$(printf '{"model":"%s","max_tokens":8,"stream":true,"messages":[{"role":"user","content":"Reply only OK"}]}' "${ANTHROPIC_DEFAULT_SONNET_MODEL}")"

unauthenticated_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  -H 'content-type: application/json' --data "${stream_body}" "${APIM_BASE_URL}/v1/messages")"
[[ "${unauthenticated_status}" == 401 ]] || {
  echo "Expected unauthenticated request to return 401; got ${unauthenticated_status}" >&2
  exit 1
}

count_response="$(curl --fail-with-body --silent "${common_headers[@]}" \
  --data "${count_body}" "${APIM_BASE_URL}/v1/messages/count_tokens")"
python3 -c 'import json,sys; assert json.load(sys.stdin)["input_tokens"] >= 0' <<<"${count_response}"

stream_response="$(curl --fail-with-body --no-buffer --silent --max-time 60 "${common_headers[@]}" \
  --data "${stream_body}" "${APIM_BASE_URL}/v1/messages")"
grep -q 'message_start' <<<"${stream_response}"
grep -q 'message_stop' <<<"${stream_response}"

echo "Post-deployment authentication, count_tokens, and SSE smoke checks passed."
