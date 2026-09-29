#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_b03_depreciation_scope_update.B03FordUpdateMaterialTest -v > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/native.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/native.exit
exit "$result"
