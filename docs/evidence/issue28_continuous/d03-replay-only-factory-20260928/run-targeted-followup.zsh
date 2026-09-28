#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
evidence=docs/evidence/issue28_continuous/d03-replay-only-factory-20260928
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u -m unittest -q \
  tests.vnext.test_d03_native_preparation.D03NativePreparationTest.test_jpm_successor_has_current_factory_identity_but_cannot_execute \
  > "$evidence/followup-targeted.log" 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
result=$?
set -e
print -r -- "$result" > "$evidence/followup-targeted.exit"
exit $result
