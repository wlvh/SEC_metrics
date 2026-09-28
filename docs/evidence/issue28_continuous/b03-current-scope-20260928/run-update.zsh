#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
export PYTHONDONTWRITEBYTECODE=1
/private/tmp/issue28_py314_venv/bin/python -m unittest \
  tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest -v
test_code=$?
print -r -- "$test_code" > docs/evidence/issue28_continuous/b03-current-scope-20260928/update.exit
exit "$test_code"
