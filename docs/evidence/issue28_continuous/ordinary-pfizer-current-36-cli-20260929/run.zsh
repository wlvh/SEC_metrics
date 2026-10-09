#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
e=docs/evidence/issue28_continuous/ordinary-pfizer-current-36-cli-20260929
export PYTHONPATH=.:scripts:tools
/private/tmp/issue28_py314_venv/bin/python "$e/run.py" > "$e/run.log" 2>&1
rc=$?
print -r -- "$rc" > "$e/run.exit"
exit "$rc"
