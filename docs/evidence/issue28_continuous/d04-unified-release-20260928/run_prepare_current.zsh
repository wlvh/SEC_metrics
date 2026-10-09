#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  /private/tmp/issue28_py314_venv/bin/python -u \
  docs/evidence/issue28_continuous/d04-unified-release-20260928/prepare_current_enphase.py \
  > docs/evidence/issue28_continuous/d04-unified-release-20260928/prepare-current.log 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
code=$?
set -e
print -r -- "$code" > docs/evidence/issue28_continuous/d04-unified-release-20260928/prepare-current.exit
exit "$code"
