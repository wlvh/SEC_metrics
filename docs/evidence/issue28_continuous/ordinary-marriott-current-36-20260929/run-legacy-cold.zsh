#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
/private/tmp/issue28_py314_venv/bin/python docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/legacy_cold.py > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/legacy-cold.log 2>&1
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/legacy-cold.exit
exit "$code"
