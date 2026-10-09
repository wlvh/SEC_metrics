#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
python3 -m unittest -v tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.test_mixed_old_root_resumes_current_rule_metric_and_c04 > docs/evidence/issue28_continuous/b03-invalid-prior-recovery-20260929/followup-material.log 2>&1
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/b03-invalid-prior-recovery-20260929/followup-material.exit
exit "$code"
