#!/bin/bash
# The positions the first batch did not reach (it died when paused), same closure and driver.
cd /tmp/claude-0/native/rt-d04
DRIVER=docs/evidence/issue47_history/targeted-round-30a7934b/targeted_runs.py
OUT=/tmp/claude-0/native/round-c02e01/out
run() { python3 $DRIVER $OUT "$1" "$2" "$3" "$4" >> /tmp/claude-0/native/round-c02e01/progress.log 2>&1; }
run c02-paramount-2025 paramount_skydance_paramount_global 2025-12-31 C02
run c02-pfizer-2025 pfizer 2025-12-31 C02
run c02-salesforce-2026 salesforce 2026-01-31 C02
run c02-southwest-2025 southwest_airlines 2025-12-31 C02
run e01-enphase-2025 enphase_energy 2025-12-31 E01
run e01-ford-2025 ford_motor_company 2025-12-31 E01
run e01-lumen-2025 lumen_technologies 2025-12-31 E01
run e01-macys-2026 macys 2026-01-31 E01
run e01-marriott-2023 marriott_international 2023-12-31 E01
run e01-marriott-2024 marriott_international 2024-12-31 E01
run e01-marriott-2025 marriott_international 2025-12-31 E01
run e01-paramount-2024 paramount_skydance_paramount_global 2024-12-31 E01
run e01-paramount-2025 paramount_skydance_paramount_global 2025-12-31 E01
run e01-pfizer-2025 pfizer 2025-12-31 E01
run e01-salesforce-2026 salesforce 2026-01-31 E01
run e01-southwest-2025 southwest_airlines 2025-12-31 E01
echo ROUND_DONE >> /tmp/claude-0/native/round-c02e01/progress.log
