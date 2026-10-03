#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
e=docs/evidence/issue28_continuous/ordinary-marriott-cli-b01-c04-20260929
/private/tmp/issue28_py314_venv/bin/python "$e/check.py" create > "$e/create.log" 2>&1
rc=$?
if (( rc == 0 )); then
  /private/tmp/issue28_py314_venv/bin/python "$e/check.py" read > "$e/read.log" 2>&1
  rc=$?
fi
print -r -- "$rc" > "$e/run.exit"
exit "$rc"
