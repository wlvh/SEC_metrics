#!/bin/bash
# Build the #54 main-integration branch from a main that already contains PR56.
#
# Usage, from any clone holding main, the PR55 delivery commit and 0bc24734:
#   bash apply-on-main.sh <main-commit> <pr55-commit> <new-branch> <new-worktree-dir>
#
# Applies only PR55's own delta (SOURCE_BASE..pr55-commit), the merged
# governance documents, the carry-manifest files (exact SOURCE_BASE blobs) and
# the final workflow. Every input is read from the fixed <pr55-commit>, never
# from the caller's working tree. It works in a new worktree on a new branch,
# never resets an existing branch, and leaves no commit when it stops.
# Only the five documents below may conflict; any other conflict, patch error,
# leftover conflict marker or out-of-scope path stops the script.
set -euo pipefail
MAIN=$1; PR55=$2; BRANCH=$3; WT=$4
SOURCE_BASE=${SOURCE_BASE:-0bc24734736bb1e6cb34fbcf7ab9fece6951764e}
VERIFIED_BASE=${VERIFIED_BASE:-0be58051d69809229ef2f3132a984d55ba5e6131}
PKG=${PKG:-docs/evidence/issue54_company/live2/pr56-integration}
DOCS=(AGENTS.md TESTING.md capability_contract.json docs/business_user_guide.md interact.md)
declare -A DRAFT=([AGENTS.md]=AGENTS.md [TESTING.md]=TESTING.md
  [capability_contract.json]=capability_contract.json
  [docs/business_user_guide.md]=docs_business_user_guide.md [interact.md]=interact.md)
WORKFLOW=.github/workflows/vnext-fast.yml
die() { echo "STOP: $*" >&2; exit 1; }

MAIN=$(git rev-parse --verify "$MAIN^{commit}"); PR55=$(git rev-parse --verify "$PR55^{commit}")
git rev-parse --verify -q "$SOURCE_BASE^{commit}" >/dev/null || die "missing $SOURCE_BASE"
git rev-parse --verify -q "refs/heads/$BRANCH" >/dev/null && die "branch $BRANCH already exists; inspect it instead of resetting"
[ -e "$WT" ] && die "worktree path $WT already exists"
for f in "${DOCS[@]}" "$WORKFLOW"; do
  git diff --quiet "$VERIFIED_BASE" "$MAIN" -- "$f" ||
    die "$f changed on main after $VERIFIED_BASE; re-merge it instead of using the verified copy"
done
git cat-file -e "$PR55:$PKG/main-retarget/carry-manifest.json" || die "materials missing in $PR55"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
git diff --binary "$SOURCE_BASE" "$PR55" > "$TMP/delta.patch"
git diff --name-only "$SOURCE_BASE" "$PR55" > "$TMP/delta-paths"
git show "$PR55:$PKG/main-retarget/carry-manifest.json" > "$TMP/carry.json"
git show "$PR55:$PKG/main-retarget/vnext-fast.main.yml" > "$TMP/workflow.yml"
for f in "${DOCS[@]}"; do git show "$PR55:$PKG/governance-merge-drafts/${DRAFT[$f]}" > "$TMP/draft-${DRAFT[$f]}"; done

git worktree add -q -b "$BRANCH" "$WT" "$MAIN"
abort() { cd /; git -C "$OLDPWD_REPO" worktree remove --force "$WT"; git -C "$OLDPWD_REPO" branch -q -D "$BRANCH"; die "$*"; }
OLDPWD_REPO=$(pwd); cd "$WT"

set +e; git apply --3way --index "$TMP/delta.patch" 2> "$TMP/apply.err"; rc=$?; set -e
mapfile -t UNMERGED < <(git diff --name-only --diff-filter=U)
if [ $rc -ne 0 ]; then
  [ ${#UNMERGED[@]} -gt 0 ] || abort "patch failed without a conflict: $(grep -m3 -E '^error' "$TMP/apply.err" | tr '\n' ' ')"
  for f in "${UNMERGED[@]}"; do
    printf '%s\n' "${DOCS[@]}" | grep -qxF "$f" || abort "unexpected conflict in $f"
  done
fi
# A verified merged document is used only where PR55's delta changes that
# document; otherwise main's version stays untouched.
CHANGED_DOCS=()
for f in "${DOCS[@]}"; do
  if grep -qxF "$f" "$TMP/delta-paths"; then cp "$TMP/draft-${DRAFT[$f]}" "$f"; CHANGED_DOCS+=("$f"); fi
done
cp "$TMP/workflow.yml" "$WORKFLOW"
python3 - "$TMP/carry.json" > "$TMP/carry-paths" <<'PY'
import json, os, subprocess, sys
m = json.load(open(sys.argv[1]))
for row in m['files']:
    raw = subprocess.check_output(['git', 'cat-file', 'blob', row['git_blob']])
    os.makedirs(os.path.dirname(row['path']) or '.', exist_ok=True)
    open(row['path'], 'wb').write(raw)
    os.chmod(row['path'], 0o755 if row['mode'] == '100755' else 0o644)
    print(row['path'])
PY
git add -- ${CHANGED_DOCS[@]+"${CHANGED_DOCS[@]}"} "$WORKFLOW"
xargs -a "$TMP/carry-paths" -d '\n' git add --
[ -z "$(git diff --name-only --diff-filter=U)" ] || abort "conflicts remain after resolution"
[ -z "$(git status --porcelain --untracked-files=all | grep -v '^[MADR] ')" ] || abort "unstaged or untracked changes: $(git status --porcelain | grep -v '^[MADR] ' | head -3 | tr '\n' ' ')"
if git diff --cached --check "$MAIN" 2>&1 | grep -q 'leftover conflict marker'; then abort "leftover conflict marker"; fi
if git diff --cached "$MAIN" -U0 | grep -qE '^\+(<{7}|>{7})( |$)'; then abort "conflict marker text staged"; fi
# Scope: every changed path must come from PR55's delta, the carry manifest or the workflow.
cat "$TMP/delta-paths" "$TMP/carry-paths" <(echo "$WORKFLOW") | sort -u > "$TMP/allowed"
OUT=$(git diff --cached --name-only "$MAIN" | sort -u | comm -23 - "$TMP/allowed")
[ -z "$OUT" ] || abort "out-of-scope paths: $(echo "$OUT" | head -5 | tr '\n' ' ')"
git -c user.name="${GIT_AUTHOR_NAME:-issue54 integration}" -c user.email="${GIT_AUTHOR_EMAIL:-noreply@localhost}" \
  commit -q -m "Issue #54 on main: company delta from $PR55, inherited coverage and CI jobs"
echo "created $BRANCH at $(git rev-parse HEAD) in $WT from main $MAIN and PR55 $PR55"
