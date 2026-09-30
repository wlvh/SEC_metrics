#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts:tools
export ISSUE28_MARRIOTT_PRIVATE_ROOT=/private/tmp/issue28-b03-marriott-namespace-repair-20261001
export ISSUE28_MARRIOTT_RECORD_SUFFIX=-repair
export ISSUE28_MARRIOTT_BASE_SHA=7bb17621c45545449f9dce390a41f39ec4bd0208
/private/tmp/issue28_py314_venv/bin/python \
  docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/exercise.py \
  > docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/exercise-repair.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/exercise-repair.exit
exit "$result"
