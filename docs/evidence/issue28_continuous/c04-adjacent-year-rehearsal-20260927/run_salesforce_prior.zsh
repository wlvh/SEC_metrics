#!/bin/zsh
set -e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u \
  docs/evidence/issue28_continuous/c04-adjacent-year-rehearsal-20260927/rehearse.py \
  --salesforce --prior-only \
  > docs/evidence/issue28_continuous/c04-adjacent-year-rehearsal-20260927/salesforce-prior.log 2>&1 < /dev/null &
wait $!
