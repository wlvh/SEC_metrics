#!/bin/bash
# Receiver snapshot step 2: offline history runs of the public company CLI for
# each registered company, one fresh work/output dir per company (no existing
# state is touched). Saved sources only, sockets disabled (net_guard.py), no
# model/SEC/paid calls. Window = the company's five labels in inputs/periods.
# usage: run_history_lanes.sh CODE_ROOT SOURCE_ROOT D04_PACKAGE OUT_BASE lane1 "c1 c2" lane2 "c3 c4" ...
set -u
CODE=$1; SRC=$2; PKG=$3; BASE=$4; shift 4
HERE=$(cd "$(dirname "$0")" && pwd)
PERIODS=$HERE/../inputs/periods
ARGS=""; for m in $(cat "$HERE/metric_ids.txt"); do ARGS="$ARGS --metric $m"; done
window() { # company -> "first last" issuer fiscal-year label of its resolved window
  python3 -I -c 'import json,sys; w=json.load(open(sys.argv[1]))["companies"][sys.argv[2]]["window"]; print(w[0], w[-1])' \
    "$PERIODS/$1.json" "$1"; }
run_company() {
  local c=$1; local d=$BASE/$c; mkdir -p $d
  read -r ys ye <<< "$(window $c)"
  local t0=$(date +%s)
  timeout 5400 python3 -I -B "$HERE/net_guard.py" $CODE/tools/vnext_company.py run --company $c \
    --period fiscal-years --fiscal-year-start $ys --fiscal-year-end $ye --source-root $SRC \
    --work-dir $d/work --output-dir $d/out --saved-call-package $PKG $ARGS > $d/run.json 2> $d/run.err
  local rc=$?
  echo "{\"company\":\"$c\",\"exit\":$rc,\"start_fy\":$ys,\"end_fy\":$ye,\"seconds\":$(( $(date +%s)-t0 ))}" > $d/done.json
  python3 -I -B "$HERE/net_guard.py" $CODE/tools/vnext_company.py results --company $c \
    --state-root $d/work --output-root $d/results-read > $d/results.json 2> $d/results.err
}
while [ $# -ge 2 ]; do
  lane=$1; companies=$2; shift 2
  ( for c in $companies; do run_company $c; done; echo done > $BASE/lane-$lane.done ) &
done
wait
