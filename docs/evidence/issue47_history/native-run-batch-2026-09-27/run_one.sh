#!/bin/bash
# One period of the full-frame batch: every runnable metric, in the runtime tree.
cd /tmp/claude-0/native/rt-d04
OUT=/tmp/claude-0/native/batch-latest
label=$1; company=$2; end=$3; metrics=$4
python3 docs/evidence/issue47_history/targeted-round-30a7934b/targeted_runs.py $OUT $label $company $end $metrics > $OUT/$label.log 2>&1
echo "$label EXIT $?" >> $OUT/progress.log
