#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
e=docs/evidence/issue28_continuous/b13-reference-coverage-scan-v2-20261001
export PYTHONPATH=.:scripts
/private/tmp/issue28_py314_venv/bin/python -m unittest \
  tests.vnext.test_capacity_two_stage_material.CapacityTwoStageMaterialTest.test_complete_reference_coverage_scan_records_only_shape_credit \
  > "$e/material-recorded.log" 2>&1
result=$?
print -r -- "$result" > "$e/material-recorded.exit"
exit "$result"
