#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
e=docs/evidence/issue28_continuous/d03-registered-full-review-20260929
/private/tmp/issue28_py314_venv/bin/python "$e/cold.py" > "$e/cold.log" 2>&1
rc=$?
print -r -- "$rc" > "$e/cold.exit"
exit "$rc"
