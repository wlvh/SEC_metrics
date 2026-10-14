#!/bin/bash
# Receiver snapshot v1.1: resume the offline JPMorgan history run (same args as run_history_lanes.sh, longer timeout).
S=/home/user/SEC_metrics/docs/receiver/progress_snapshot_v1/scripts; d=/home/user/acc/snap/hist/jpmorgan_chase
ARGS=""; for m in $(cat $S/metric_ids.txt); do ARGS="$ARGS --metric $m"; done
t0=$(date +%s)
timeout 36000 python3 -I -B $S/net_guard.py /home/user/acc/p269/tools/vnext_company.py run --company jpmorgan_chase --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2025 --source-root /home/user/acc/hist-src/source-inputs --work-dir $d/work --output-dir $d/out --saved-call-package /home/user/acc/d04pkg/model-ledger.tar.gz $ARGS > $d/run.json 2> $d/run.err
rc=$?
echo "{\"company\":\"jpmorgan_chase\",\"exit\":$rc,\"start_fy\":2021,\"end_fy\":2025,\"seconds\":$(( $(date +%s)-t0 )),\"restart\":true}" > $d/done.json
python3 -I -B $S/net_guard.py /home/user/acc/p269/tools/vnext_company.py results --company jpmorgan_chase --state-root $d/work --output-root $d/results-read > $d/results.json 2> $d/results.err
