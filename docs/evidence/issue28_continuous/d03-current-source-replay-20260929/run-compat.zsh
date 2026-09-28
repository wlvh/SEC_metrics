#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts:.
/private/tmp/issue28_py314_venv/bin/python -m unittest -v \
  tests.vnext.test_continuous_semantic_calls \
  tests.vnext.test_r6_regulatory_semantics \
  tests.vnext.test_d03_native_assessment.D03NativeAssessmentTest \
  > docs/evidence/issue28_continuous/d03-current-source-replay-20260929/compat.log 2>&1
rc=$?
print -r -- "$rc" > docs/evidence/issue28_continuous/d03-current-source-replay-20260929/compat.exit
exit "$rc"
