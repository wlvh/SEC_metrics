#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts
/private/tmp/issue28_py314_venv/bin/python tools/run_fast_tests_v2.py --jobs 2 \
  > docs/evidence/issue28_continuous/d03-context-only-summary-20260930/fast.json \
  2> docs/evidence/issue28_continuous/d03-context-only-summary-20260930/fast.stderr
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/d03-context-only-summary-20260930/fast.exit
exit "$result"
