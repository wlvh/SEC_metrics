#!/bin/zsh
set +e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u tools/run_fast_tests_v2.py --jobs 2 &
pid=$!
wait $pid
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/b13-native-currency-context-20260930/repair-fast.exit
exit "$code"
