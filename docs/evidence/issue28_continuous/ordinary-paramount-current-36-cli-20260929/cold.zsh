#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
python3 docs/evidence/issue28_continuous/ordinary-paramount-current-36-cli-20260929/cold.py > docs/evidence/issue28_continuous/ordinary-paramount-current-36-cli-20260929/cold.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/ordinary-paramount-current-36-cli-20260929/cold.exit
exit "$result"
