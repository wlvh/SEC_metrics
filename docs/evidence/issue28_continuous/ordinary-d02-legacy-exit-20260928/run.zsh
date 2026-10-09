#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
PYTHONPATH=.:scripts:tools /private/tmp/issue28_py314_venv/bin/python -u \
  docs/evidence/issue28_continuous/ordinary-d02-legacy-exit-20260928/probe.py \
  > docs/evidence/issue28_continuous/ordinary-d02-legacy-exit-20260928/run.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/ordinary-d02-legacy-exit-20260928/run.exit
exit $result
