#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
evidence=docs/evidence/issue28_continuous/ordinary-scalability-audit-20260928
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u \
  tools/run_fast_tests_v2.py --suite fast --jobs 1 \
  > "$evidence/fast.log" 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
code=$?
set -e
print -r -- "$code" > "$evidence/fast.exit"
exit "$code"
