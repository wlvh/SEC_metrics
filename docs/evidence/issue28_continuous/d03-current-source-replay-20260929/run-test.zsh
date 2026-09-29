#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts:.
/private/tmp/issue28_py314_venv/bin/python -m unittest -v tests.vnext.test_d03_current_source_replay > docs/evidence/issue28_continuous/d03-current-source-replay-20260929/test.log 2>&1
rc=$?
print -r -- "$rc" > docs/evidence/issue28_continuous/d03-current-source-replay-20260929/test.exit
exit "$rc"
