#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
root=docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929
: > "$root/split-salesforce-summary.tsv"
for name in current legacy; do
  start=$(date +%s)
  case "$name" in
    current) selector=tests.vnext.test_b03_depreciation_scope_update.B03CurrentUpdateMaterialTest;;
    legacy) selector=tests.vnext.test_b03_depreciation_scope_update.B03LegacyRecoveryMaterialTest;;
  esac
  python3 -m unittest -v "$selector" > "$root/split-$name.log" 2>&1
  code=$?
  end=$(date +%s)
  print -r -- "$name\t$code\t$((end-start))" >> "$root/split-salesforce-summary.tsv"
  if (( code != 0 )); then exit "$code"; fi
done
