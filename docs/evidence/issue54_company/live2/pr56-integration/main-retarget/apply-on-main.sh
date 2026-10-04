#!/bin/bash
# Rebuild the verified PR55-on-main content after PR56 has entered main.
#
# Usage (from a clone that has main, PR55's branch and 0bc24734 objects):
#   bash apply-on-main.sh <main-commit-containing-PR56> <PR55-head> <work-branch>
#
# It applies only PR55's own delta (0bc24734..PR55-head, 3-way), the merged
# governance documents, the inherited company-pipeline coverage files listed
# in carry-manifest.json (exact 0bc24734 blobs) and the final workflow. No
# history is rewritten; review the result, then bring it into PR55 by the
# agreed retarget procedure. Verified once on PR56 0be58051 (README.md here).
set -euo pipefail
MAIN=$1; PR55=$2; BRANCH=$3
HERE=$(cd "$(dirname "$0")" && pwd)
DRAFTS=$HERE/../governance-merge-drafts
# Main-side documents changed after 0be58051 must be re-merged by hand, not overwritten.
for f in AGENTS.md TESTING.md capability_contract.json docs/business_user_guide.md interact.md .github/workflows/vnext-fast.yml; do
  if ! git diff --quiet 0be58051d69809229ef2f3132a984d55ba5e6131 "$MAIN" -- "$f"; then
    echo "STOP: $f changed on main after 0be58051; re-merge it instead of using the verified copy" >&2; exit 1
  fi
done
git checkout -q -B "$BRANCH" "$MAIN"
git diff --binary 0bc24734 "$PR55" > /tmp/pr55-delta.patch
git apply --3way --index /tmp/pr55-delta.patch || true
cp "$DRAFTS/AGENTS.md" AGENTS.md
cp "$DRAFTS/TESTING.md" TESTING.md
cp "$DRAFTS/capability_contract.json" capability_contract.json
cp "$DRAFTS/docs_business_user_guide.md" docs/business_user_guide.md
cp "$DRAFTS/interact.md" interact.md
cp "$HERE/vnext-fast.main.yml" .github/workflows/vnext-fast.yml
python3 - "$HERE/carry-manifest.json" <<'PY'
import json, subprocess, sys, os
m = json.load(open(sys.argv[1]))
for row in m['files']:
    raw = subprocess.check_output(['git', 'cat-file', 'blob', row['git_blob']])
    os.makedirs(os.path.dirname(row['path']) or '.', exist_ok=True)
    open(row['path'], 'wb').write(raw)
    if row['mode'] == '100755':
        os.chmod(row['path'], 0o755)
print('carried', len(m['files']), 'files from', m['source_commit'])
PY
git add -A
if git diff --cached --name-only --diff-filter=U | grep -q .; then
  echo "Unresolved conflicts remain" >&2; exit 1
fi
git -c user.name="${GIT_AUTHOR_NAME:-PR55 retarget}" -c user.email="${GIT_AUTHOR_EMAIL:-noreply@localhost}" \
  commit -q -m "PR55 on main: company delta, merged governance documents, inherited coverage and CI jobs"
git log --oneline -1
