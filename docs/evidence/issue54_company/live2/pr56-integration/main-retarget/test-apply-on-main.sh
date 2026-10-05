#!/bin/bash
# Small throwaway-repository checks for apply-on-main.sh (no project data).
#   A: only the expected document conflicts -> branch and one commit created
#   B: an unexpected code conflict          -> stops, no branch, no commit
#   C: leftover conflict marker in a draft  -> stops, no branch, no commit
set -euo pipefail
SCRIPT=$(cd "$(dirname "$0")" && pwd)/apply-on-main.sh
ROOT=$(mktemp -d); trap 'rm -rf "$ROOT"' EXIT
PKG=docs/evidence/issue54_company/live2/pr56-integration
DOCS="AGENTS.md TESTING.md capability_contract.json docs/business_user_guide.md interact.md"
g() { git -c user.name=t -c user.email=t@localhost "$@"; }

make_repo() {  # $1 = repo dir, $2 = main code.py content, $3 = draft AGENTS content
  local R=$1; mkdir -p "$R"; cd "$R"; git init -q -b base0
  mkdir -p docs tests .github/workflows
  for f in $DOCS; do echo "base $f" > "$f"; done
  echo "v0" > code.py; echo "carried test" > tests/carried.py; echo "old wf" > .github/workflows/vnext-fast.yml
  g add -A; g commit -q -m base0; BASE0=$(git rev-parse HEAD)
  CARRY_BLOB=$(git rev-parse HEAD:tests/carried.py)
  git checkout -q -b pr55
  echo "pr55 doc line" >> AGENTS.md; echo "pr55 testing line" >> TESTING.md; printf 'v0\npr55 change\n' > code.py
  mkdir -p "$PKG/main-retarget" "$PKG/governance-merge-drafts"
  for f in AGENTS.md TESTING.md capability_contract.json docs_business_user_guide.md interact.md; do
    echo "merged $f" > "$PKG/governance-merge-drafts/$f"; done
  printf '%s\n' "$3" > "$PKG/governance-merge-drafts/AGENTS.md"
  echo "final wf" > "$PKG/main-retarget/vnext-fast.main.yml"
  printf '{"source_commit":"%s","files":[{"path":"tests/carried.py","mode":"100644","git_blob":"%s"}]}\n' "$BASE0" "$CARRY_BLOB" \
    > "$PKG/main-retarget/carry-manifest.json"
  g add -A; g commit -q -m pr55; PR55=$(git rev-parse HEAD)
  git checkout -q --orphan main; git read-tree --empty; git clean -fdxq
  mkdir -p docs .github/workflows
  for f in $DOCS; do echo "main $f" > "$f"; done
  printf '%s\n' "$2" > code.py; echo "main wf" > .github/workflows/vnext-fast.yml
  g add -A; g commit -q -m main; MAIN=$(git rev-parse HEAD)
  git checkout -q base0
}
run_case() {  # $1 name, $2 main code.py, $3 draft AGENTS, $4 expect ok|stop
  local R=$ROOT/$1; make_repo "$R" "$2" "$3"
  set +e; out=$(SOURCE_BASE=$BASE0 VERIFIED_BASE=$MAIN GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@localhost \
    bash "$SCRIPT" "$MAIN" "$PR55" integ "$R-wt" 2>&1); rc=$?; set -e
  local branch=$(git rev-parse -q --verify refs/heads/integ || true)
  if [ "$4" = ok ]; then
    [ $rc -eq 0 ] && [ -n "$branch" ] || { echo "FAIL $1: expected success: $out"; exit 1; }
    [ "$(git -C "$R-wt" rev-list --count "$MAIN"..integ)" = 1 ] || { echo "FAIL $1: commit count"; exit 1; }
    [ "$(git show integ:AGENTS.md)" = "$3" ] && [ "$(git show integ:tests/carried.py)" = "carried test" ] &&
      [ "$(git show integ:.github/workflows/vnext-fast.yml)" = "final wf" ] &&
      git show integ:code.py | grep -q "pr55 change" &&
      [ "$(git show integ:TESTING.md)" = "merged TESTING.md" ] &&
      [ "$(git show integ:interact.md)" = "main interact.md" ] || { echo "FAIL $1: content"; exit 1; }
  else
    [ $rc -ne 0 ] && [ -z "$branch" ] && [ ! -e "$R-wt" ] || { echo "FAIL $1: expected stop with no branch/worktree: rc=$rc $out"; exit 1; }
  fi
  echo "PASS $1 ($4): $(echo "$out" | tail -1)"
}
run_case A_expected_doc_conflict "v0" "merged AGENTS.md" ok
run_case B_unexpected_code_conflict "main code change" "merged AGENTS.md" stop
run_case C_leftover_marker "v0" $'<<<<<<< ours\nmerged\n=======\nother\n>>>>>>> theirs' stop
