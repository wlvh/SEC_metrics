#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
e=docs/evidence/issue28_continuous/b13-reference-coverage-scan-v2-20261001
export PYTHONPATH=.:scripts
/private/tmp/issue28_py314_venv/bin/python tools/run_fast_tests_v2.py --jobs 2 \
  > "$e/fast-final.json" 2> "$e/fast-final.stderr"
result=$?
print -r -- "$result" > "$e/fast-final.exit"
exit "$result"
