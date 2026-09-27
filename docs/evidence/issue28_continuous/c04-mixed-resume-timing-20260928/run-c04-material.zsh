#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
evidence=docs/evidence/issue28_continuous/c04-mixed-resume-timing-20260928
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_c04_update_cycle.C04UpdateCycleMaterialTest.test_saved_marriott_positive_creates_native_result \
  > "$evidence/c04-material.log" 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
result=$?
set -e
print -r -- "$result" > "$evidence/c04-material.exit"
exit $result
