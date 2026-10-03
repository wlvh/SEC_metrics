#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
evidence=docs/evidence/issue28_continuous/d03-recorded-interpretation-bridge-20260928
set +e
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u "$evidence/run-recorded.py" \
  > "$evidence/run.log" 2>&1
result=$?
set -e
print -r -- "$result" > "$evidence/run.exit"
exit $result
