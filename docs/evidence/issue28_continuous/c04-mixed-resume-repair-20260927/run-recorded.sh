#!/bin/sh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
base=docs/evidence/issue28_continuous/c04-mixed-resume-repair-20260927
PYTHONPATH=scripts:. uv run --offline --with tokenizers==0.22.2 python -m unittest tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_mixed_old_root_refreshes_only_c04_and_blocks_other_metrics > "$base/mixed-two-step.log" 2>&1
test_exit=$?
printf '%s\n' "$test_exit" > "$base/mixed-two-step.exit"
exit "$test_exit"
