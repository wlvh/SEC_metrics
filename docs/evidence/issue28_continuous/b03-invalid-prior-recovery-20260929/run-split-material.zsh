#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
root=docs/evidence/issue28_continuous/b03-invalid-prior-recovery-20260929
: > "$root/split-summary.tsv"
for name in salesforce southwest source; do
  start=$(date +%s)
  case "$name" in
    salesforce) selector=tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest;;
    southwest) selector=tests.vnext.test_b03_depreciation_scope_update.B03SouthwestUpdateMaterialTest;;
    source) selector=tests.vnext.test_b03_depreciation_scope.B03DepreciationScopeMaterialTest;;
  esac
  python3 -m unittest -v "$selector" > "$root/split-$name.log" 2>&1
  code=$?
  end=$(date +%s)
  print -r -- "$name\t$code\t$((end-start))" >> "$root/split-summary.tsv"
  if (( code != 0 )); then exit "$code"; fi
done
