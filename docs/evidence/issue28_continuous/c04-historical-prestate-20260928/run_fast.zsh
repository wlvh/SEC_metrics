#!/bin/zsh
set -e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u \
  tools/run_fast_tests_v2.py --suite fast \
  > docs/evidence/issue28_continuous/c04-historical-prestate-20260928/fast.log 2>&1 < /dev/null &
wait $!
