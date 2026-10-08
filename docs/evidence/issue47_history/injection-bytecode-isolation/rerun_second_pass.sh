#!/bin/bash
# Second pass: the batch script retargeted to today's code, and the E01 item-text
# injections whose target code still exists.
R=${1:?a fresh clone of the commit to re-run in}
S=$(dirname "$R")
cd "$R" || exit 2
H=docs/evidence/issue47_history
# The batch script is the retargeted one in any commit after 6923b19e; the 2026-09-29
# run copied it into a clone of 6923b19e before it was committed.
python3 - <<'PY'
from pathlib import Path
p = Path("docs/evidence/issue47_history/e01-item-text/fault_injections.py")
t = p.read_text()
marker = "\n\ndef _isolated_env():"
assert t.count(marker) == 1
subset = ("\n\n# Rerun only: the injections whose target text still exists (the others target the\n"
          "# keyword branch that 629f1ed8 replaced with content confirmation).\n"
          "SKIPPED = [i[0] for i in INJECTIONS if (REPO / i[1]).read_text().count(i[2]) != 1]\n"
          "INJECTIONS = [i for i in INJECTIONS if (REPO / i[1]).read_text().count(i[2]) == 1]\n"
          "print('skipped', SKIPPED, flush=True)")
Path("docs/evidence/issue47_history/e01-item-text/fault_injections_subset.py").write_text(
    t.replace(marker, subset + marker))
PY
run() { echo "=== $1 start $(date -u +%H:%M:%S)"; shift; timeout 7200 python3 "$@"; echo "=== exit $? $(date -u +%H:%M:%S)"; }
run batch $H/acquisition-wiring/batch_injections.py
run e01_subset $H/e01-item-text/fault_injections_subset.py $S/e01-item-subset-rerun.json
echo "ALL DONE 2"
