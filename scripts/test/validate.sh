#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${repo_root}"

while IFS= read -r file; do
  bash -n "${file}"
  shellcheck "${file}"
done < <(find scripts -type f -name '*.sh' | sort)

while IFS= read -r file; do
  python3 -m py_compile "${file}"
done < <(find scripts -type f -name '*.py' | sort)
python3 -m unittest discover -s scripts/test -p 'test_*.py'
python3 migration/tofu/test_generate_import_manifest.py

python3 - <<'PY'
from pathlib import Path
import re

for page in Path(".").glob("**/*.md"):
    if ".terraform" in page.parts:
        continue
    for target in re.findall(r"\[[^]]*\]\(([^ )#]+)", page.read_text()):
        if "://" not in target and not target.startswith("mailto:"):
            assert (page.parent / target).exists(), f"broken Markdown link: {page} -> {target}"
PY

tofu -chdir=infra/tofu fmt -check
tofu -chdir=infra/tofu init -input=false -backend=false -lockfile=readonly
tofu -chdir=infra/tofu validate

scan_status=0
grep -R -l -E '(listSecrets|ANTHROPIC_(API_KEY|AUTH_TOKEN)=|Ocp-Apim-Subscription-Key:|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
  README.md CLAUDE.md docs infra apim scripts migration .github --exclude='validate.sh' --exclude='*.pyc' --exclude='*.pyo' \
  --exclude-dir='.terraform' --exclude-dir='__pycache__' || scan_status=$?
case "${scan_status}" in
  0)
    echo "Forbidden production credential pattern found" >&2
    exit 1
    ;;
  1) ;;
  *)
    echo "Credential scan failed" >&2
    exit 1
    ;;
esac

echo "Validation checks passed."
