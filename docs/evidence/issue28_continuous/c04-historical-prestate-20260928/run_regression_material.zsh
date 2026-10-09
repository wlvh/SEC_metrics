#!/bin/zsh
set -e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_mixed_old_root_resumes_current_rule_metric_and_c04 \
  tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_failed_processing_copy_preserves_recorded_capture_for_resume \
  > docs/evidence/issue28_continuous/c04-historical-prestate-20260928/regression-material.log 2>&1 < /dev/null &
wait $!
