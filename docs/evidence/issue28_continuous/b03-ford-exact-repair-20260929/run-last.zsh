#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
PYTHONPATH=scripts:. python3 -m unittest -v \
  tests.vnext.test_b03_depreciation_scope_update.B03LegacyRecoveryMaterialTest.test_old_success_has_no_current_credit_but_new_input_can_attempt > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/last-followup.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/last-followup.exit
exit "$result"
