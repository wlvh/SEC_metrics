#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
root=docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929
: > "$root/material-followup-summary.tsv"
for name in southwest salesforce ford; do
  start=$(date +%s)
  case "$name" in
    southwest) selector=tests.vnext.test_b03_depreciation_scope_update.B03SouthwestUpdateMaterialTest;;
    salesforce) selector=tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest;;
    ford) selector=tests.vnext.test_b03_depreciation_scope_update.B03FordUpdateMaterialTest;;
  esac
  python3 -m unittest -v "$selector" > "$root/material-followup-$name.log" 2>&1
  code=$?
  end=$(date +%s)
  print -r -- "$name\t$code\t$((end-start))" >> "$root/material-followup-summary.tsv"
  if (( code != 0 )); then exit "$code"; fi
done
