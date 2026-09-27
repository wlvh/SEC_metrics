#!/bin/sh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
base=docs/evidence/issue28_continuous/c04-mixed-auto-refresh-20260927
PYTHONPATH=scripts:. uv run --offline --with tokenizers==0.22.2 python -m unittest tests.vnext.test_c04_update_cycle.C04UpdateCycleMaterialTest > "$base/c04-update-ci-targeted.log" 2>&1
update_exit=$?
printf '%s\n' "$update_exit" > "$base/c04-update-ci-targeted.exit"
PYTHONPATH=scripts:. uv run --offline --with tokenizers==0.22.2 python -m unittest tests.vnext.test_c04_refresh_cycle.C04RefreshCycleMaterialTest > "$base/c04-refresh-ci-targeted.log" 2>&1
refresh_exit=$?
printf '%s\n' "$refresh_exit" > "$base/c04-refresh-ci-targeted.exit"
test "$update_exit" -eq 0 && test "$refresh_exit" -eq 0
