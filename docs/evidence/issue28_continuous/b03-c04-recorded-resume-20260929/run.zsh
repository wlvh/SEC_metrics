#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
python3 docs/evidence/issue28_continuous/b03-c04-recorded-resume-20260929/probe.py > docs/evidence/issue28_continuous/b03-c04-recorded-resume-20260929/run-v4.log 2>&1
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/b03-c04-recorded-resume-20260929/run-v4.exit
exit "$code"
