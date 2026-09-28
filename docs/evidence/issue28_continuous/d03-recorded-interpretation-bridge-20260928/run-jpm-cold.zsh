#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
evidence=docs/evidence/issue28_continuous/d03-recorded-interpretation-bridge-20260928
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u "$evidence/cold-jpm.py" \
  > "$evidence/jpm-cold.log" 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
result=$?
set -e
print -r -- "$result" > "$evidence/jpm-cold.exit"
exit $result
