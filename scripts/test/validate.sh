#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${repo_root}"

# Shell lint (syntax).
while IFS= read -r f; do
  bash -n "$f"
done < <(find scripts -type f -name '*.sh' | sort)

# Python syntax checks.
while IFS= read -r f; do
  python3 -m py_compile "$f"
done < <(find scripts -type f -name '*.py' | sort)

# APIM policy guardrails.
policy_file="apim/policies/claude-messages.xml"
rg -q '<validate-azure-ad-token' "$policy_file"
rg -q '<authentication-managed-identity' "$policy_file"
rg -q 'exists-action="delete"' "$policy_file"
rg -q '<llm-token-limit' "$policy_file"

echo "Validation checks passed."
