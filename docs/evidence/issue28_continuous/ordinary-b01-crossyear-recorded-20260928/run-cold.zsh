#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup zsh -c '
  set -eu
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONPATH=.:scripts
  /private/tmp/issue28_py314_venv/bin/python -u \
    /private/tmp/issue28-b01-crossyear-cold-auto-one.py \
    a12d76356c3f4ad98b4d8694bc870b90 2024
  /private/tmp/issue28_py314_venv/bin/python -u \
    /private/tmp/issue28-b01-crossyear-cold-auto-one.py \
    7580564edd1a4a22948f4fa5e7172b53 2025
' > /private/tmp/issue28-b01-crossyear-cold-auto.log 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
result=$?
set -e
print -r -- "$result" > /private/tmp/issue28-b01-crossyear-cold-auto.exit
exit $result
