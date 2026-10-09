#!/bin/sh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
PYTHONPATH=scripts:. uv run --offline --with tokenizers==0.22.2 python -m unittest tests.vnext.test_c04_source_only_install > docs/evidence/issue28_continuous/c04-mixed-auto-refresh-20260927/mixed-route-test.log 2>&1
test_exit=$?
printf '%s\n' "$test_exit" > docs/evidence/issue28_continuous/c04-mixed-auto-refresh-20260927/mixed-route-test.exit
exit "$test_exit"
