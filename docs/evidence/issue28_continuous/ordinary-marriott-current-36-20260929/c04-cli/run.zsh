#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
/private/tmp/issue28_py314_venv/bin/python docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/c04-cli/run.py create > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/c04-cli/create.log 2>&1
rc=$?
if (( rc == 0 )); then
  /private/tmp/issue28_py314_venv/bin/python docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/c04-cli/run.py read > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/c04-cli/cold.log 2>&1
  rc=$?
fi
print -r -- "$rc" > docs/evidence/issue28_continuous/ordinary-marriott-current-36-20260929/c04-cli/run.exit
exit "$rc"
