#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
export PYTHONPATH=scripts
/private/tmp/issue28_py314_venv/bin/python tools/run_fast_tests_v2.py --jobs 2 > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/fast.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/fast.exit
exit "$result"
