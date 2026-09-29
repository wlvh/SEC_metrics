#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
e=docs/evidence/issue28_continuous/e01-item-source-v1-20260929
/private/tmp/issue28_py314_venv/bin/python -m unittest -v tests.vnext.test_e01_item_source > "$e/directed.log" 2>&1
rc=$?
print -r -- "$rc" > "$e/directed.exit"
if (( rc == 0 )); then
  /private/tmp/issue28_py314_venv/bin/python tools/run_fast_tests_v2.py --suite fast --jobs 2 > "$e/fast.log" 2>&1
  rc=$?
fi
print -r -- "$rc" > "$e/fast.exit"
exit "$rc"
