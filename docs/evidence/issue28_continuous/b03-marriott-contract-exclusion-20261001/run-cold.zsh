#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=.:scripts
/private/tmp/issue28_py314_venv/bin/python \
  docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/cold.py \
  > docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/cold.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/b03-marriott-contract-exclusion-20261001/cold.exit
exit "$result"
