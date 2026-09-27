#!/bin/zsh
set -e
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -u \
  docs/evidence/issue28_continuous/c04-resume-timing-20260927/profile_one.py \
  > docs/evidence/issue28_continuous/c04-resume-timing-20260927/profile-one.log 2>&1 < /dev/null &
wait $!
