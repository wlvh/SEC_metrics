"""Apply each injection in place, run the named tests, restore; record what caught it.

Usage (from the repository root, clean tree):
    python3 docs/evidence/issue47_history/block-resident-filings/fault_injections.py \
        docs/evidence/issue47_history/block-resident-filings/fault-injections.json

Each file is restored from its own bytes in a ``finally`` block, so an
interrupted run leaves no injection behind.
"""
import json, shutil, subprocess, sys
from pathlib import Path
import atexit
import os
import tempfile
REPO = Path(__file__).resolve().parents[4]


def _isolated_env():
    """The environment for one injected run: bytecode read and written only in a fresh directory.

    Restoring a file's bytes does not restore what runs. The interpreter trusts
    a cached compile whose recorded source size and whole-second modification
    time match the file, so an edit of the same size, restored within the same
    second, leaves the injected bytecode in the checkout's __pycache__ to run
    in place of the restored source. Measured 2026-09-29: a restored C02
    reader ran an injection's pattern in the next ordinary test run. No
    injected run here reads or writes the checkout's __pycache__.
    """
    cache = tempfile.mkdtemp(prefix="issue47-injection-pyc-")
    atexit.register(shutil.rmtree, cache, True)
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


T = "tests.vnext.test_historical_filing_inventory"
INJECTIONS = [
 ("COMPANY_FACTS_PROVES_THE_TARGET_AGAINST_THE_MAIN_INDEX", "scripts/vnext/historical_results.py",
  "                                                       listed_in, concepts)",
  "                                                       inventory, concepts)",
  [T + ".TheRoutesAnswerTheSameWhereverTheRowIsListed"]),
 ("ACCESSION_PROVES_THE_TARGET_AGAINST_THE_MAIN_INDEX", "scripts/vnext/historical_accession_results.py",
  "    inventory = filing_inventory(reader=reader, inventory=inventory,",
  "    _unused = filing_inventory if False else None\n    inventory = inventory if True else filing_inventory(reader=reader, inventory=inventory,",
  [T + ".TheRoutesAnswerTheSameWhereverTheRowIsListed"]),
 ("REVENUE_PROVES_THE_TARGET_AGAINST_THE_MAIN_INDEX", "scripts/vnext/historical_zero_ai_results.py",
  '        manifest = _exact_set(prepared, listed_in, facts_source, "companyfacts")',
  '        manifest = _exact_set(prepared, inventory, facts_source, "companyfacts")',
  [T + ".TheRoutesAnswerTheSameWhereverTheRowIsListed"]),
 ("FINANCIAL_ASKS_ONLY_THE_MAIN_INDEX", "scripts/vnext/historical_financial_results.py",
  '    selection = period_selection or {"loaded_inventories": [main["proof"]["document_name"]]}',
  '    selection = {"loaded_inventories": [main["proof"]["document_name"]]}',
  [T + ".TheRoutesAnswerTheSameWhereverTheRowIsListed"]),
 ("LOOKUP_SEARCHES_EVERY_DECLARED_BLOCK", "scripts/vnext/historical_filing_inventory.py",
  "    for block_name in loaded[1:]:",
  "    for block_name in sorted(declared):",
  [T]),
 ("LOOKUP_SKIPS_THE_RANGE_CHECK", "scripts/vnext/historical_filing_inventory.py",
  "        _need(history_body_alignment(shard=declared[block_name], rows=rows) is None,",
  "        _need(True or history_body_alignment(shard=declared[block_name], rows=rows) is None,",
  [T]),
 ("LOOKUP_ACCEPTS_A_ROW_TWO_BLOCKS_LIST", "scripts/vnext/historical_filing_inventory.py",
  '    _need(len(holding) == 1, "HISTORICAL_FILING_ROW_IN_MORE_THAN_ONE_BLOCK:" + accession)',
  '    _need(len(holding) >= 1, "HISTORICAL_FILING_ROW_IN_MORE_THAN_ONE_BLOCK:" + accession)',
  [T]),
 ("LOOKUP_RETURNS_AN_EQUAL_COPY_OF_THE_MAIN_INDEX", "scripts/vnext/historical_filing_inventory.py",
  "        return inventory\n",
  "        return dict(inventory)\n",
  [T]),
]
out = []
for name, path, old, new, tests in INJECTIONS:
    target = REPO / path
    original = target.read_bytes()
    text = original.decode("utf-8")
    assert text.count(old) == 1, (name, text.count(old))
    try:
        target.write_text(text.replace(old, new), encoding="utf-8")
        run = subprocess.run([sys.executable, "-m", "unittest", *tests], cwd=REPO, env=_isolated_env(),
                             capture_output=True, text=True, timeout=2400)
        tail = run.stderr.strip().splitlines()
        failed = sorted({line.split(" (")[0].replace("FAIL: ", "").replace("ERROR: ", "")
                         for line in tail if line.startswith(("FAIL:", "ERROR:"))})
        out.append({"id": name, "file": path, "outcome": "CAUGHT" if run.returncode else "NOT_CAUGHT",
                    "caught_by": failed, "suite_result": tail[-1] if tail else ""})
    finally:
        target.write_bytes(original)
    print(json.dumps(out[-1]), flush=True)
Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
