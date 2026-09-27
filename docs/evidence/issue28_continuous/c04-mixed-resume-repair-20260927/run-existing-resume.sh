#!/bin/sh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 1
base=docs/evidence/issue28_continuous/c04-mixed-resume-repair-20260927
PYTHONPATH=scripts:. uv run --offline --with tokenizers==0.22.2 python -m unittest tests.vnext.test_c04_refresh_resume.C04RefreshResumeMaterialTest > "$base/c04-only-resume-current.log" 2>&1
test_exit=$?
printf '%s\n' "$test_exit" > "$base/c04-only-resume-current.exit"
exit "$test_exit"
