#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
e=docs/evidence/issue28_continuous/ordinary-ford-current-36-cli-20260929
export PYTHONPATH=.:scripts:tools
/private/tmp/issue28_py314_venv/bin/python "$e/cold.py" > "$e/cold.log" 2>&1
rc=$?
print -r -- "$rc" > "$e/cold.exit"
exit "$rc"
