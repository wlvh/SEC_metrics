#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts:.
/private/tmp/issue28_py314_venv/bin/python docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/cold.py > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/cold.log 2>&1
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/cold.exit
exit "$code"
