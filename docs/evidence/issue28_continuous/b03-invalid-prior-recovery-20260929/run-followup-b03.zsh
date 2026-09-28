#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
python3 -m unittest -v tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest > docs/evidence/issue28_continuous/b03-invalid-prior-recovery-20260929/followup-b03.log 2>&1
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/b03-invalid-prior-recovery-20260929/followup-b03.exit
exit "$code"
