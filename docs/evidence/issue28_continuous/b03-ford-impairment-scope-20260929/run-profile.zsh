#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
python3 -m cProfile -o /private/tmp/issue28-b03-southwest-20260929.prof -m unittest -v tests.vnext.test_b03_depreciation_scope_update.B03SouthwestUpdateMaterialTest > docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929/profile-southwest.log 2>&1
code=$?
print -r -- "$code" > docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929/profile-southwest.exit
if (( code == 0 )); then
python3 - <<'PY' > docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929/profile-summary.log
import pstats
s=pstats.Stats('/private/tmp/issue28-b03-southwest-20260929.prof')
s.strip_dirs().sort_stats('cumtime').print_stats(35)
PY
fi
exit "$code"
