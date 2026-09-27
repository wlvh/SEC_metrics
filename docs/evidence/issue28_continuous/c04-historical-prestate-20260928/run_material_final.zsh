#!/bin/zsh
set -e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_historical_b01_pointer_without_new_attempt_can_resume \
  > docs/evidence/issue28_continuous/c04-historical-prestate-20260928/material-final.log 2>&1 < /dev/null &
wait $!
