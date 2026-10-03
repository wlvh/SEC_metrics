#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
e=docs/evidence/issue28_continuous/ordinary-marriott-cli-b01-c04-20260929
/private/tmp/issue28_py314_venv/bin/python "$e/check.py" repeat > "$e/repeat.log" 2>&1
rc=$?
print -r -- "$rc" > "$e/repeat.exit"
exit "$rc"
