#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
python3 docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929/c04_regression.py > docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929/c04-regression.log 2>&1
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929/c04-regression.exit
exit "$code"
