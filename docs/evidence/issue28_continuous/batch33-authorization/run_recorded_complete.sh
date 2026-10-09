#!/bin/sh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 99
printf 'STARTED\n' > docs/evidence/issue28_continuous/batch33-authorization/recorded-complete-enphase.started
PYTHONPATH=scripts:. /tmp/sec_metrics_ci_20260922_venv/bin/python \
  docs/evidence/issue28_continuous/batch33-authorization/recorded_complete_enphase.py \
  > docs/evidence/issue28_continuous/batch33-authorization/recorded-complete-enphase.log 2>&1
status=$?
printf '%s\n' "$status" > docs/evidence/issue28_continuous/batch33-authorization/recorded-complete-enphase.exit
exit "$status"
