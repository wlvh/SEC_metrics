#!/bin/zsh
set -e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_continuous_sec_acquisition.ContinuousSecAcquisitionTest.test_recorded_capture_failure_isolation_native_http_and_checkpoint_binding \
  > docs/evidence/issue28_continuous/c04-historical-prestate-20260928/default-sec.log 2>&1 < /dev/null &
wait $!
