"""Undo each part of the history-block coherence rule and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

With names, only those injections run (the control still runs every module).

Each injection edits one rule file in place (exactly one match, must compile),
runs the coherence module - and, for the two catalog loaders, the module whose
case reads real saved blocks through that loader - with a fresh bytecode
prefix, and restores the bytes. The control run of every module must pass
first; the script exits 1 unless every injection is caught by the case named
for it. Zero calls.

It edits the tree it lives in, so nothing else may import from or read that
tree while it runs.
"""
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = "scripts/vnext/normal_history_catalog.py"
LOOKUP = "scripts/vnext/historical_filing_inventory.py"
C04 = "scripts/vnext/historical_governance_results.py"
EVENTS = "scripts/vnext/historical_event_walk.py"
COHERENCE = "tests.vnext.test_history_block_coherence"
CATALOG_CASES = "tests.vnext.test_normal_history_catalog"
PERIOD_CASES = "tests.vnext.test_historical_metadata_context"
MODULES = (COHERENCE, CATALOG_CASES, PERIOD_CASES)
LOADER_CALL = """        problem = history_block_coherence(shard=shard, body=body, rows=shard_rows,
                                          last_day=last_days[shard["name"]])
        if problem:
            limitations.append({"kind": "HISTORY_SHARD_SNAPSHOT_CONFLICT", **problem})
        rows.extend(shard_rows)
        names.append(shard["name"])
    accessions = [row["accessionNumber"] for row in rows]
    _need(len(accessions) == len(set(accessions)), "HISTORY_INVENTORY_ACCESSIONS_OVERLAP")
"""
FROZEN_LOADER_CALL = """        from .normal_governance_input import history_body_alignment
        problem = history_body_alignment(shard=shard, rows=shard_rows)
        if problem:
            limitations.append({"kind": "HISTORY_SHARD_SNAPSHOT_CONFLICT", **problem})
        rows.extend(shard_rows)
        names.append(shard["name"])
    accessions = [row["accessionNumber"] for row in rows]
    _need(len(accessions) == len(set(accessions)), "HISTORY_INVENTORY_ACCESSIONS_OVERLAP")
"""
WINDOW_TAIL = """    annual = sorted((row for row in rows if row["form"] in ANNUAL_FORMS),
                    key=lambda row: (row["reportDate"], row["filingDate"], row["accessionNumber"]))
    boundary = window_end()
"""
PERIOD_TAIL = """    annual = sorted((row for row in rows if row["form"] in ANNUAL_FORMS),
                    key=lambda row: (row["reportDate"], row["filingDate"], row["accessionNumber"]))
    unloaded = sorted("""

# name: (file, old, new, the case written for it[, the module that holds it])
INJECTIONS = {
    "THE_GAP_DAY_IS_NOT_ADMITTED": (
        CATALOG,
        """        last_days[shard["name"]] = max(shard["filingTo"], day_before)""",
        """        last_days[shard["name"]] = shard["filingTo"]""",
        "test_a_filing_on_the_gap_day_is_in_the_older_block"),
    "THE_GAP_REACHES_INTO_THE_NEXT_BLOCK": (
        CATALOG,
        """        day_before = (date.fromisoformat(newer_start) - DAY).isoformat()""",
        """        day_before = newer_start""",
        "test_a_filing_on_the_next_block_s_first_day_is_outside"),
    "A_BLOCK_MAY_END_BEFORE_ITS_DECLARED_END": (
        CATALOG,
        """        last_days[shard["name"]] = max(shard["filingTo"], day_before)""",
        """        last_days[shard["name"]] = day_before""",
        "test_a_block_never_ends_before_its_declared_end"),
    "THE_NEWEST_BLOCK_IGNORES_THE_RECENT_LIST": (
        CATALOG,
        """                       else (min(recent) if recent else None))""",
        """                       else None)""",
        "test_each_block_ends_the_day_before_the_next_newer_one_starts"),
    "THE_COUNT_IS_NOT_COMPARED": (
        CATALOG,
        """    if type(declared) is not int or declared != len(dates):
        failed.append("FILING_COUNT_DIFFERS_FROM_DECLARED")
""", "",
        "test_a_block_missing_filings_is_not_the_declared_block"),
    "A_MISSING_COUNT_IS_TRUSTED": (
        CATALOG,
        """    if type(declared) is not int or declared != len(dates):""",
        """    if type(declared) is int and declared != len(dates):""",
        "test_a_block_without_a_declared_count_is_not_trusted"),
    "ONLY_THE_KEPT_FORMS_ARE_COUNTED": (
        CATALOG,
        """    if type(declared) is not int or declared != len(dates):""",
        """    if type(declared) is not int or declared != len(rows):""",
        "test_the_count_is_every_filing_not_only_the_forms_the_catalog_keeps"),
    "ONLY_THE_KEPT_FORMS_ARE_DATED": (
        CATALOG,
        """    outside = [value for value in dates if not shard["filingFrom"] <= value <= last_day]""",
        """    outside = [row["filingDate"] for row in rows
               if not shard["filingFrom"] <= row["filingDate"] <= last_day]""",
        "test_the_dates_are_every_filing_s_not_only_the_kept_forms"),
    "ANY_STALE_BLOCK_BLOCKS_EVERY_PERIOD": (
        CATALOG,
        """           and (prior_end is None or item["block_last_day"] > prior_end)""",
        """           and True""",
        "test_a_block_ending_before_the_prior_period_blocks_nothing"),
    "THE_DECLARED_END_DECIDES": (
        CATALOG,
        """item["block_last_day"] > prior_end""",
        """item["declared_filing_to"] > prior_end""",
        "test_the_block_s_last_day_not_its_declared_end_decides"),
    "THE_OLDEST_PERIOD_IS_NOT_BLOCKED": (
        CATALOG,
        """           and (prior_end is None or item["block_last_day"]""",
        """           and (prior_end is not None and item["block_last_day"]""",
        "test_the_oldest_period_is_blocked_by_any_stale_block"),
    "THE_WINDOW_LOADER_KEEPS_THE_FROZEN_CHECK": (
        CATALOG, LOADER_CALL + WINDOW_TAIL, FROZEN_LOADER_CALL + WINDOW_TAIL,
        "test_window_loads_only_the_history_a_bounded_window_can_need", CATALOG_CASES),
    "THE_PERIOD_LOADER_KEEPS_THE_FROZEN_CHECK": (
        CATALOG, LOADER_CALL + PERIOD_TAIL, FROZEN_LOADER_CALL + PERIOD_TAIL,
        "test_on_the_saved_blocks_the_stale_block_is_named", PERIOD_CASES),
    "THE_TARGET_LOOKUP_KEEPS_THE_FROZEN_CHECK": (
        LOOKUP,
        """        _need(history_block_coherence(shard=declared[block_name], body=body, rows=rows,
                                      last_day=last_days[block_name]) is None,""",
        """        from .normal_governance_input import history_body_alignment
        _need(history_body_alignment(shard=declared[block_name], rows=rows) is None,""",
        "test_the_target_lookup_takes_a_fresh_block_with_a_gap_day_filing"),
    "THE_PRIOR_WALK_KEEPS_THE_FROZEN_CHECK": (
        LOOKUP,
        """        need(history_block_coherence(shard=shard, body=body, rows=values,
                                     last_day=last_days[shard["name"]]) is None,""",
        """        from .normal_governance_input import history_body_alignment
        need(history_body_alignment(shard=shard, rows=values) is None,""",
        "test_a_filing_on_the_gap_day_no_longer_stops_the_walk"),
    "C04_S_WALK_KEEPS_THE_FROZEN_CHECK": (
        C04,
        """        conflict = history_block_coherence(shard=shard, body=data, rows=shard_rows,
                                           last_day=last_days[shard["name"]])""",
        """        from .normal_governance_input import history_body_alignment
        conflict = history_body_alignment(shard=shard, rows=shard_rows)""",
        "test_c04_s_walk_takes_a_fresh_block_with_a_gap_day_filing"),
    "THE_EVENT_WALK_KEEPS_THE_FROZEN_CHECK": (
        EVENTS,
        """    walk = _view(frozen._event_sources, history_body_alignment=coherence)""",
        """    walk = frozen._event_sources""",
        "test_a_fresh_block_with_a_gap_day_filing_is_read"),
    "THE_EVENT_WALK_COUNTS_THE_ROWS_IT_IS_HANDED": (
        EVENTS,
        """        return history_block_coherence(shard=shard, body=strict_json_loads(text=raw.decode("utf-8")),""",
        """        return history_block_coherence(shard=shard, body={"filingDate": [row["filingDate"] for row in rows]},""",
        "test_a_fresh_block_with_a_gap_day_filing_is_read"),
    "THE_REGISTERED_WALK_KEEPS_THE_FROZEN_WALK": (
        EVENTS,
        """    walk = _view(frozen._registered_event_sources, _event_sources=event_sources)""",
        """    walk = frozen._registered_event_sources""",
        "test_the_registered_walk_walks_each_cik_with_the_successor"),
    "AN_UNREFERENCED_NAME_IS_BOUND_SILENTLY": (
        EVENTS,
        """    _need(set(names) <= set(function.__code__.co_names),""",
        """    _need(True,""",
        "test_a_name_the_frozen_code_does_not_use_is_refused"),
}


def run(modules):
    """Each module in its own process; the failed case names across them."""
    failed, codes, started = set(), [], time.time()
    for module in modules:
        env = {**os.environ, "PYTHONPYCACHEPREFIX": tempfile.mkdtemp()}
        done = subprocess.run([sys.executable, "-m", "unittest", module], cwd=REPO, env=env,
                              capture_output=True, text=True, timeout=3600)
        codes.append(done.returncode)
        failed |= {line.split(" ")[1] for line in done.stderr.splitlines()
                   if line.startswith(("FAIL: ", "ERROR: "))}
    return codes, sorted(failed), int(time.time() - started)


def main(out, names):
    chosen = {name: INJECTIONS[name] for name in (names or INJECTIONS)}
    originals = {name: (REPO / name).read_bytes() for name in (CATALOG, LOOKUP, C04, EVENTS)}
    for name, (target, old, *_rest) in chosen.items():
        if originals[target].decode("utf-8").count(old) != 1:
            raise SystemExit("INJECTION_DOES_NOT_MATCH_ONCE:" + name)
    results = {}
    codes, failed, seconds = run(MODULES)
    if any(codes) or failed:
        raise SystemExit("CONTROL_FAILED:%s %s" % (codes, failed))
    results["CONTROL"] = {"returncodes": codes, "seconds": seconds}
    try:
        for name, (target, old, new, expected, *module) in chosen.items():
            path = REPO / target
            path.write_bytes(originals[target].decode("utf-8").replace(old, new).encode("utf-8"))
            py_compile.compile(str(path), doraise=True, cfile=tempfile.mktemp())
            codes, failed, seconds = run(module or [COHERENCE])
            path.write_bytes(originals[target])
            results[name] = {"file": target, "modules": module or [COHERENCE],
                             "returncodes": codes, "seconds": seconds,
                             "failed_cases": failed, "expected_case": expected,
                             "caught_by_the_case_written_for_it": expected in failed}
            print(name, results[name]["caught_by_the_case_written_for_it"], failed, flush=True)
    finally:
        for target, data in originals.items():
            (REPO / target).write_bytes(data)
    for target, data in originals.items():
        if (REPO / target).read_bytes() != data:
            raise SystemExit("TARGET_NOT_RESTORED:" + target)
    results["all_caught"] = all(results[name]["caught_by_the_case_written_for_it"]
                                for name in chosen)
    Path(out).write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_caught": results["all_caught"]}), flush=True)
    return 0 if results["all_caught"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
