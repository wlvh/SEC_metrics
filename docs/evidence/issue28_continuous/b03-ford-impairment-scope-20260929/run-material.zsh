#!/bin/zsh
cd /Users/lyuhongwang/Developer/SEC_metrics || exit 2
export PYTHONPATH=scripts
root=docs/evidence/issue28_continuous/b03-ford-impairment-scope-20260929
: > "$root/material-summary.tsv"
for name in ford southwest; do
  start=$(date +%s)
  case "$name" in
    ford) selector=tests.vnext.test_b03_depreciation_scope_update.B03FordUpdateMaterialTest;;
    southwest) selector=tests.vnext.test_b03_depreciation_scope_update.B03SouthwestUpdateMaterialTest;;
  esac
  python3 -m unittest -v "$selector" > "$root/material-$name.log" 2>&1
  code=$?
  end=$(date +%s)
  print -r -- "$name\t$code\t$((end-start))" >> "$root/material-summary.tsv"
  if (( code != 0 )); then exit "$code"; fi
done
