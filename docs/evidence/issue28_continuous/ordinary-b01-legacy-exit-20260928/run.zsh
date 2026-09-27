#!/bin/zsh
set -e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u \
  docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py \
  > docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/run.log 2>&1 < /dev/null &
wait $!
