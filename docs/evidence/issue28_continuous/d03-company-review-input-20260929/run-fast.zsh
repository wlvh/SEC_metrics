#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
/private/tmp/issue28_py314_venv/bin/python tools/run_fast_tests_v2.py --jobs 2 > docs/evidence/issue28_continuous/d03-company-review-input-20260929/fast.log 2>&1
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/d03-company-review-input-20260929/fast.exit
exit "$code"
