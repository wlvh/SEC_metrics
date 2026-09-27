#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_historical_b01_pointer_without_new_attempt_can_resume \
  > docs/evidence/issue28_continuous/c04-historical-prestate-20260928/atomic-material.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/c04-historical-prestate-20260928/atomic-material.exit
exit $result
