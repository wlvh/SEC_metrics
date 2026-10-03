#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
python3 docs/evidence/issue28_continuous/ci-normal-zero-ai-selector-20260929/time-classes.py > docs/evidence/issue28_continuous/ci-normal-zero-ai-selector-20260929/launcher.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/ci-normal-zero-ai-selector-20260929/launcher.exit
exit "$result"
