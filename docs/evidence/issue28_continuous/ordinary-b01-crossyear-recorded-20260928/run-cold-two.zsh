#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup zsh -c '
  set -eu
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONPATH=.:scripts
  /private/tmp/issue28_py314_venv/bin/python -u \
    /private/tmp/issue28-b01-crossyear-cold-auto-two-one.py \
    94f6e5a74b264bdfbce8548593f24405 2024
  /private/tmp/issue28_py314_venv/bin/python -u \
    /private/tmp/issue28-b01-crossyear-cold-auto-two-one.py \
    15eaf54f8a6848a99cdd1b8ac3815b9f 2025
' > /private/tmp/issue28-b01-crossyear-cold-auto-two.log 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
result=$?
set -e
print -r -- "$result" > /private/tmp/issue28-b01-crossyear-cold-auto-two.exit
exit $result
