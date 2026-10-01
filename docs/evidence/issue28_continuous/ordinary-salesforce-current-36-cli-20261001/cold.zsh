#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
python3 docs/evidence/issue28_continuous/ordinary-salesforce-current-36-cli-20261001/cold.py > docs/evidence/issue28_continuous/ordinary-salesforce-current-36-cli-20261001/cold.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/ordinary-salesforce-current-36-cli-20261001/cold.exit
exit "$result"
