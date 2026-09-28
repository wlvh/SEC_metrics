#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
evidence=docs/evidence/issue28_continuous/d03-complete-recorded-20260928
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_d03_native_assessment.D03NativeCollectionMaterialTest -v \
  > "$evidence/complete.log" 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
result=$?
set -e
print -r -- "$result" > "$evidence/complete.exit"
exit $result
