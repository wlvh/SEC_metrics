#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
export PYTHONDONTWRITEBYTECODE=1
/private/tmp/issue28_py314_venv/bin/python tools/run_fast_tests_v2.py --jobs 2
test_code=$?
print -r -- "$test_code" > docs/evidence/issue28_continuous/d03-unresolved-native-20260928/fast.exit
exit "$test_code"
