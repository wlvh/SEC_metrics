#!/bin/bash
# Re-run the nine older in-place injection scripts, one after another, in a clean clone.
R=${1:?a fresh clone of the commit to re-run in}
cd "$R" || exit 2
H=docs/evidence/issue47_history
run() { echo "=== $1 start $(date -u +%H:%M:%S)"; shift; timeout 7200 python3 "$@"; echo "=== exit $? $(date -u +%H:%M:%S)"; }
run model_start $H/model-egress/model_start_injections.py
run vm_start $H/acquisition-wiring/vm_start_injections.py
run batch $H/acquisition-wiring/batch_injections.py
run visibility $H/e01-item-text/visibility_injections.py
run e01_item $H/e01-item-text/fault_injections.py $H/e01-item-text/fault-injections.json
run block $H/block-resident-filings/fault_injections.py $H/block-resident-filings/fault-injections.json
run part_iii $H/part-iii-statement-review/fault_injections.py $H/part-iii-statement-review/fault-injections.json
run b03 $H/b03-depreciation-scope/fault_injections.py $H/b03-depreciation-scope/fault-injections.json
run b03_route $H/b03-depreciation-scope/route_fault_injections.py $H/b03-depreciation-scope/route-fault-injections.json
echo "ALL DONE"
