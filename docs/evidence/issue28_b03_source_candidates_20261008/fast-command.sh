#!/bin/sh
cd /Users/lyuhongwang/.codex/worktrees/issue28-b03-source/SEC_metrics || exit 2
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:tools /private/tmp/issue28-company-c02-venv-20261006/bin/python tools/run_foundation_ci.py --suite fast > docs/evidence/issue28_b03_source_candidates_20261008/fast.log 2>&1
rc=$?
printf '%s\n' "$rc" > docs/evidence/issue28_b03_source_candidates_20261008/fast.exit
exit "$rc"
