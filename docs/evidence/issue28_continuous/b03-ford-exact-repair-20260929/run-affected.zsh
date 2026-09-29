#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics
PYTHONPATH=scripts:. python3 -m unittest -v \
  tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest \
  tests.vnext.test_b03_depreciation_scope_update.B03LegacyRecoveryMaterialTest \
  tests.vnext.test_b03_depreciation_scope_update.B03SouthwestUpdateMaterialTest \
  tests.vnext.test_b03_depreciation_scope_update.B03HistoricalRecoveryVerifierTest \
  tests.vnext.test_normal_run_v3_material.OrdinaryIntegratedMaterialTest > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/affected.log 2>&1
result=$?
print -r -- "$result" > docs/evidence/issue28_continuous/b03-ford-exact-repair-20260929/affected.exit
exit "$result"
