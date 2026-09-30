#!/bin/zsh
set +e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u \
  docs/evidence/issue28_continuous/ordinary-marriott-b03-failure-isolation-20260930/run.py &
pid=$!
wait $pid
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/ordinary-marriott-b03-failure-isolation-20260930/run.exit
exit "$code"
