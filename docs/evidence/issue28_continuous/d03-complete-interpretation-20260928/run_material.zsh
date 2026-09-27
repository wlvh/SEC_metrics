#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u -m unittest \
  tests.vnext.test_d03_complete_interpretation.D03CompleteInterpretationTest.test_current_saved_marriott_requires_every_response_and_preserves_uncertainty \
  > docs/evidence/issue28_continuous/d03-complete-interpretation-20260928/material.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/d03-complete-interpretation-20260928/material.exit
exit $result
