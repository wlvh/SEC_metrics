#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_d03_native_preparation \
  > docs/evidence/issue28_continuous/d03-native-preparation-20260928/final.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/d03-native-preparation-20260928/final.exit
exit $result
