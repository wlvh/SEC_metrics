#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_d03_native_preparation.D03NativePreparationTest.test_saved_jpm_source_uses_anchor_successor_without_losing_groups \
  > docs/evidence/issue28_continuous/d03-native-preparation-20260928/material.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/d03-native-preparation-20260928/material.exit
exit $result
