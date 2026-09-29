#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
PYTHONPATH=scripts:. python3 docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/cold-ford-35.py > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/ford-35-cold.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/ford-35-cold.exit
exit "$result"
