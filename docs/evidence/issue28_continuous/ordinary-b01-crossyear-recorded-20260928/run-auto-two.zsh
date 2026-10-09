#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u \
  /private/tmp/issue28-b01-crossyear-auto-two.py \
  > /private/tmp/issue28-b01-crossyear-auto-two.log 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
result=$?
set -e
print -r -- "$result" > /private/tmp/issue28-b01-crossyear-auto-two.exit
exit $result
