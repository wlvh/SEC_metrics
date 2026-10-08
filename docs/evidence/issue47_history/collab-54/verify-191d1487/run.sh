#!/bin/bash
set -u
S=/tmp/claude-0/-home-user-SEC-metrics/a7365d9c-a812-5427-8542-fc0481eaa53f/scratchpad
C=$S/c54e
R=$C/r191
CO=paramount_skydance_paramount_global
P=$C/prog
t() { date +%s; }
cd $P
s=$(t); python3 tools/vnext_company.py export --history-years 5 --source-root $C/prepared/source-inputs/source-inputs \
  --output-root $C/transfer-191 --trust-root $C/trust-191 --company $CO --metric C01 > $R/export.json 2> $R/export.err
echo "export rc=$? secs=$(( $(t)-s ))" >> $R/steps.txt
git stash push -q -- requirements scripts && git status --porcelain > $R/unpatched-status.txt
s=$(t); python3 tools/vnext_company.py install-runtime --kind historical --output-root $C/runtime-h191 > $R/runtime.json 2> $R/runtime.err
git stash pop -q && git status --porcelain > $R/repatched-status.txt
echo "install-runtime rc=$? secs=$(( $(t)-s ))" >> $R/steps.txt
s=$(t); python3 $C/runtime-h191/tools/vnext_company.py install --package-root $C/transfer-191 --state-root $C/state-191/$CO \
  --trust-root $C/trust-191 --company $CO > $R/install.json 2> $R/install.err
echo "install rc=$? secs=$(( $(t)-s ))" >> $R/steps.txt
s=$(t); python3 $C/runtime-h191/tools/vnext_company.py compute --state-root $C/state-191/$CO --trust-root $C/trust-191 \
  --company $CO --metric C01 --report-end 2024-12-31 > $R/compute.json 2> $R/compute.err
echo "compute rc=$? secs=$(( $(t)-s ))" >> $R/steps.txt
cd $C/runtime-h191
s=$(t); SEC_METRICS_SOURCE_TRUST_ROOT=$C/trust-191 python3 /home/user/SEC_metrics/docs/evidence/issue47_history/collab-54/verify-2a642e56/compare.py \
  $C/state-191/$CO $CO 2024-12-31 $R/direct-2024.json $R/compare.json > $R/compare.out 2> $R/compare.err
echo "compare rc=$? secs=$(( $(t)-s ))" >> $R/steps.txt
echo DONE >> $R/steps.txt
