#!/bin/bash
# Twelve E01 periods under the committed closure, one after the other, in the runtime tree.
cd /tmp/claude-0/native/rt-d04
D=docs/evidence/issue47_history/targeted-round-30a7934b/targeted_runs.py
OUT=/tmp/claude-0/native/e01-targeted
for spec in enphase-2025:enphase_energy:2025-12-31 ford-2025:ford_motor_company:2025-12-31 \
            lumen-2025:lumen_technologies:2025-12-31 macys-2026:macys:2026-01-31 \
            marriott-2023:marriott_international:2023-12-31 marriott-2024:marriott_international:2024-12-31 \
            marriott-2025:marriott_international:2025-12-31 \
            paramount-2024:paramount_skydance_paramount_global:2024-12-31 \
            paramount-2025:paramount_skydance_paramount_global:2025-12-31 \
            pfizer-2025:pfizer:2025-12-31 salesforce-2026:salesforce:2026-01-31 \
            southwest-2025:southwest_airlines:2025-12-31; do
  IFS=: read label company end <<< "$spec"
  python3 $D $OUT $label $company $end E01 > $OUT/$label.log 2>&1
  echo "$label EXIT $?" >> $OUT/progress.log
done
echo DONE >> $OUT/progress.log
