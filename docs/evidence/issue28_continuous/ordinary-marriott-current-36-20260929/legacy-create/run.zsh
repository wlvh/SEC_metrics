#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
/private/tmp/issue28_py314_venv/bin/python docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/legacy-create/run.py > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/legacy-create/run.log 2>&1
rc=$?
print -r -- "$rc" > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/legacy-create/run.exit
exit "$rc"
