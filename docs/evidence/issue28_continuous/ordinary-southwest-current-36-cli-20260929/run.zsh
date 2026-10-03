#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
e=docs/evidence/issue28_continuous/ordinary-southwest-current-36-cli-20260929
/private/tmp/issue28_py314_venv/bin/python "$e/run.py" > "$e/run.log" 2>&1
rc=$?
print -r -- "$rc" > "$e/run.exit"
exit "$rc"
