#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
evidence=docs/evidence/issue28_continuous/c04-recovery-credit-20260928
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u \
  tools/run_fast_tests_v2.py --suite fast --jobs 2 \
  > "$evidence/fast.log" 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
result=$?
set -e
print -r -- "$result" > "$evidence/fast.exit"
exit $result
