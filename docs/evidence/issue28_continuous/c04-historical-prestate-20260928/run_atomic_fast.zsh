#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u \
  tools/run_fast_tests_v2.py --suite fast \
  > docs/evidence/issue28_continuous/c04-historical-prestate-20260928/atomic-fast.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/c04-historical-prestate-20260928/atomic-fast.exit
exit $result
