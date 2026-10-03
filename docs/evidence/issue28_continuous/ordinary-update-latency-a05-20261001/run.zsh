#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
e=docs/evidence/issue28_continuous/ordinary-update-latency-a05-20261001
export PYTHONPATH=.:scripts:tools
/private/tmp/issue28_py314_venv/bin/python "$e/profile_a05.py" > "$e/run-final.log" 2>&1
result=$?
print -r -- "$result" > "$e/run-final.exit"
exit "$result"
