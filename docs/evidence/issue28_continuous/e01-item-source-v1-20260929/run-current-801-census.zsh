#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
PYTHONPATH=scripts:. python3 docs/evidence/issue28_continuous/e01-item-source-v1-20260929/census-current-801.py > docs/evidence/issue28_continuous/e01-item-source-v1-20260929/current-801-census.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/e01-item-source-v1-20260929/current-801-census.exit
exit "$result"
