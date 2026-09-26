#!/bin/bash
# Fault injections for the proposal tool's not-yet-declarable check.
#
# Each injection breaks one side - the plan's stated meaning or the grant
# object - and requires tools/propose_historical_allowance.py to refuse without
# writing the proposal. The files are restored afterwards and compared byte for
# byte. Run from the repository root; zero SEC or provider calls.
set -u
S=$(mktemp -d)
PLAN=docs/evidence/issue47_history/acquisition-plan.json
TOOL=tools/propose_historical_allowance.py
PROP=docs/evidence/issue47_history/acquisition-wiring/proposed-allowance.json
cp "$PLAN" "$S/plan.bak"; cp "$TOOL" "$S/tool.bak"; cp "$PROP" "$S/prop.bak"
run() {
  out=$(timeout 1200 python3 "$TOOL" 2>&1); rc=$?
  last=$(echo "$out" | tail -1 | cut -c1-160)
  if cmp -s "$PROP" "$S/prop.bak"; then untouched=yes; else untouched=NO; fi
  echo "$1 rc=$rc proposal_untouched=$untouched :: $last"
}
# 1. The plan states the old meaning: the unreached chains outside every grant.
python3 - <<'PY'
import json
p = "docs/evidence/issue47_history/acquisition-plan.json"
d = json.load(open(p, encoding="utf-8"))
for statement in d["revision_5"]["not_yet_declarable"].values():
    statement["outside_every_grant"] = sorted(statement["outside_every_grant"]
                                              + statement["admitted_once_declarable"])
    statement["admitted_once_declarable"] = []
open(p, "w", encoding="utf-8").write(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
PY
run PLAN_STATES_THE_OLD_MEANING
cp "$S/plan.bak" "$PLAN"
# 2. The annual-chain grant is narrowed to exclude the bank; the text is unchanged.
python3 - <<'PY'
p = "tools/propose_historical_allowance.py"
s = open(p, encoding="utf-8").read()
old = '{"grant": "A_ANNUAL_CHAIN", "company_ids": EVERYONE,'
assert s.count(old) == 1
open(p, "w", encoding="utf-8").write(
    s.replace(old, '{"grant": "A_ANNUAL_CHAIN", "company_ids": OTHERS,'))
PY
run GRANT_NARROWED_TEXT_UNCHANGED
cp "$S/tool.bak" "$TOOL"
# 3. The annual-chain grant starts a year late, so it covers only some unreached years.
python3 - <<'PY'
p = "tools/propose_historical_allowance.py"
s = open(p, encoding="utf-8").read()
old = ('     "dependency_classes": ["ACCESSION_INSTANCE_DISCOVERY", "ANNUAL_PERIOD_IDENTITY"],\n'
       '     "earliest_report_end": WINDOW[0], "latest_report_end": WINDOW[1]},')
assert s.count(old) == 1
open(p, "w", encoding="utf-8").write(s.replace(old, old.replace(
    'WINDOW[0], "latest', 'str(int(WINDOW[0][:4]) + 1) + WINDOW[0][4:], "latest')))
PY
run GRANT_COVERS_ONLY_SOME_YEARS
cp "$S/tool.bak" "$TOOL"
cmp "$PLAN" "$S/plan.bak" && cmp "$TOOL" "$S/tool.bak" && cmp "$PROP" "$S/prop.bak" \
  && echo RESTORED_BYTE_FOR_BYTE
rm -rf "$S"
