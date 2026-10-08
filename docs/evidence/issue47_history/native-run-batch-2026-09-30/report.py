"""Write the full-frame batch report from what the batch and the frame recorded.

Nothing here is typed in. The positions come from ``plan.tsv`` (written by
``batch_plan.py`` from the coverage frame's own three tests), what happened to
each comes from the driver's per-period ``matrix-<label>.json`` (including the
separate-process read-back of every frozen Run), the layered counts come from
the coverage frame built over the batch's own run directories, and the tree
comparison comes from the two minted manifests.

Positions that ran without a value are split by reason code into four kinds,
and a reason code this script has not been told about stops it: a report that
quietly files an unknown reason under "gap" says something nobody checked.

Usage (after the batch has finished; the frame driver writes one directory per
period, and its run directories are moved into ``<batch>/runs`` first):
    python3 report.py <batch directory> <runtime manifest> <output directory> <batch commit> [<source root>]

``<runtime manifest>`` is the minted ``baseline_manifest.json`` of the runtime
tree the batch ran in (the repository commit's files plus the registration
patch), kept beside the batch because the runtime tree moves on.

``<batch commit>`` is the repository commit whose rule files the runtime tree
carried. The two-tree comparison reads the repository's manifest at that commit,
not the checkout's: the checkout moves on while a batch runs, and a comparison
with a later snapshot would report the later work as a difference between the
trees. What changed in the rule files since is listed apart.
"""
import collections
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BATCH, RUNTIME_MANIFEST, OUT = (Path(argument) for argument in sys.argv[1:4])
COMMIT = sys.argv[4]

# What a withheld or valueless result means, by the reason code the route wrote.
ANSWERS = {  # the Spec's answer about the company, not a missing value
    "ANNUAL_DURATION_OUT_OF_RANGE", "DENOMINATOR_NONPOSITIVE", "RATIO_NUMERATOR_NOT_POSITIVE",
    "ENTITY_CONTINUITY_NOT_COMPARABLE"}
DECIDED = {  # an approved policy refusing an input class: a decided question
    "HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED"}
AWAITING_MODEL = {  # the route is wired and stops where an owner-approved call must answer
    "HISTORICAL_E01_CONTENT_CONFIRMATION_NOT_REGISTERED"}
METHOD_LIMITS = {  # a named withhold where the method cannot prove the value
    "B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN", "HISTORICAL_E01_ITEM_TEXT_DOES_NOT_SETTLE_IT",
    # The approved C03 reads one CEO/PEO total; a year reporting two PEOs
    # (Paramount FY2024: Bakish and McCarthy) has no single one to read.
    "C03_MULTIPLE_REPORTED_AMOUNTS",
    # A nil target-year total for a former PEO with no name facts binding him
    # elsewhere (Ford's 2024 and 2025 proxies); the frozen placeholder rule
    # needs those name facts, so the resolver cannot tell it from a conflict.
    "C03_TARGET_FACT_INVALID"}
GAPS = {  # a named material or implementation gap
    "ALL_BRANCHES_REJECTED", "B06_CURRENT_INPUT_UNRESOLVED", "B06_SOURCE_RELATIONSHIP_UNRESOLVED",
    "C03_SUPPORTED_CURRENT_SOURCE_NOT_FOUND", "C04_COMPARABLE_AUDITOR_FACTS_MISSING",
    "HISTORICAL_B06_SOURCE_ROUTE_UNRESOLVED", "HISTORICAL_COMPANYFACTS_ROUTE_UNRESOLVED",
    "HISTORICAL_GOVERNANCE_SOURCE_ROUTE_UNRESOLVED", "HISTORICAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED"}
# Named gaps this batch met that a commit after the batch commit closes; the
# targeted round at the later closure re-runs each position.
FIXED_AFTER = {"HISTORICAL_LODGING_SOURCE_ROUTE_UNRESOLVED": "older introduction wording (5866cbc1)"}
# Failed attempts, by the category the route's exception carried or, where it
# carried none, the reason code its message starts with (every message these
# routes raise starts with one). Nothing after the first colon is read.
FAILED_KINDS = {
    "XBRL source contains no contexts": ("a 2022 proxy without inline XBRL; fixed after the batch "
                                         "commit (0ec71207 cover identity, 825cc5f9 table reader)"),
    "TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE": ("page numbers and parenthesized note numbers; fixed "
                                                   "after the batch commit (2df677bf, 536fd980)"),
    "SEMANTIC_SINGLE_SOURCE_OBJECT_EXCEEDS_INPUT_BOUND": ("one inline continuation over the frozen "
                                                          "byte bound; fixed after the batch commit (8997e8c5)"),
    "MODEL_REVIEW_NOT_EXECUTED": "wired; stops where an owner-approved model call must answer",
    "HISTORICAL_TEXT_RUN_INPUT_BLOCKED": ("the Run's input could not be prepared; the route's own "
                                          "limitation list, kept verbatim in the error, names each "
                                          "missing source")}


def _failure_kind(row):
    return row.get("category") or row["error"].split(":", 1)[0]


def main():
    plan = [line.rstrip("\n").split("\t") for line in (BATCH / "plan.tsv").read_text().splitlines()]
    planned = {(label, metric) for label, _, _, metrics in plan for metric in metrics.split(",")}
    rows, per_period = [], []
    for label, company, end, metrics in plan:
        matrix = json.loads((BATCH / label / ("matrix-" + label + ".json")).read_text())
        positions = matrix["positions"]
        for row in positions:
            if (row["company_id"], row["report_end"]) != (company, end):
                raise SystemExit("A_MATRIX_ROW_IS_NOT_ITS_PERIOD:" + label)
        rows.extend(positions)
        per_period.append({"case": label, "company_id": company, "report_end": end,
                           "attempted": len(positions),
                           "duration_seconds": matrix["duration_seconds"],
                           "stages": dict(sorted(collections.Counter(r["stage"] for r in positions).items())),
                           "failures": [{"metric_id": r["metric_id"], "category": r.get("category"),
                                         "error_type": r.get("error_type"), "error": r.get("error")}
                                        for r in positions if r["stage"] == "FAILED"]})
    attempted = {(r["case"], r["metric_id"]) for r in rows}
    if attempted != planned or len(rows) != len(planned):
        raise SystemExit("THE_BATCH_DID_NOT_ATTEMPT_EXACTLY_ITS_PLAN:missing="
                         + str(sorted(planned - attempted)) + ":extra=" + str(sorted(attempted - planned)))

    frozen = [r for r in rows if r["stage"] == "PUBLIC_ROW"]
    replayed = [r for r in frozen if r.get("separate_process_replay", {}).get("status") == "FROZEN"
                and r["separate_process_replay"]["run_id"] == r["run_id"]
                and r["separate_process_replay"]["result_id"] == r["result_id"]]
    closures = sorted({r["requirement_closure_hash"] for r in frozen})
    if len(closures) != 1:
        raise SystemExit("MORE_THAN_ONE_CLOSURE:" + str(closures))
    calls = collections.Counter()
    for r in frozen:
        calls.update(r["new_calls"])

    failed = [r for r in rows if r["stage"] == "FAILED"]
    unknown = sorted({_failure_kind(r) for r in failed} - set(FAILED_KINDS), key=str)
    if unknown:
        raise SystemExit("A_FAILED_KIND_THIS_REPORT_HAS_NOT_BEEN_TOLD_ABOUT:" + str(unknown))

    no_value = [r for r in frozen if r.get("value") in (None, "")]
    by_reason = collections.Counter(r["reason_code"] for r in no_value)
    kinds = {"an_answer_about_the_company": ANSWERS, "an_approved_policy_refusing_an_input_class": DECIDED,
             "awaiting_an_owner_decision_on_model_calls": AWAITING_MODEL,
             "a_named_method_limit": METHOD_LIMITS, "a_named_material_or_implementation_gap": GAPS,
             "a_program_gap_fixed_after_the_batch_commit": set(FIXED_AFTER)}
    unknown = sorted(set(by_reason) - set().union(*kinds.values()))
    # A structural non-applicability is not a missing value; it is counted apart.
    structural = [r for r in no_value if r["reason_code"] == "TRAIT_NOT_APPLICABLE"]
    unknown = [code for code in unknown if code != "TRAIT_NOT_APPLICABLE"]
    if unknown:
        raise SystemExit("A_REASON_CODE_THIS_REPORT_HAS_NOT_BEEN_TOLD_ABOUT:" + str(unknown))
    split = {kind: {code: by_reason[code] for code in sorted(codes) if by_reason[code]}
             for kind, codes in kinds.items()}

    attempts = BATCH / "attempts"
    for label, _, _, _ in plan:
        matrix = json.loads((BATCH / label / ("matrix-" + label + ".json")).read_text())
        target = attempts / label / "native-run-matrix.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"record_type": "HISTORICAL_NATIVE_RUN_MATRIX",
                                      "converted_from": "matrix-" + label + ".json",
                                      "positions": matrix["positions"]}, indent=1, sort_keys=True))
    frame_path = BATCH / "frame.json"
    # The batch ran on the root restored from the acquisition's export; its
    # periods are planned there, or the frame reads them as "original not saved".
    source_root = [] if len(sys.argv) < 6 else ["--source-root", sys.argv[5]]
    subprocess.run([sys.executable, "tools/vnext_history_coverage.py", *source_root,
                    "--runs-root", str(BATCH / "runs"),
                    "--requirement-closure-hash", closures[0], "--attempts-root", str(attempts),
                    "--output", str(frame_path)], cwd=str(REPO), check=True,
                   stdout=subprocess.DEVNULL)
    frame = json.loads(frame_path.read_text())

    periods = {(company, end) for _, company, end, _ in plan}
    per_period_frame = {}
    for position in frame["positions"]:
        key = (position["company_id"], position["report_end"])
        if key not in periods:
            continue
        entry = per_period_frame.setdefault(key[0] + " " + key[1], collections.Counter())
        entry["status:" + position["status"]] += 1
        entry["content_accepted"] += bool(position["delivery"]["content_acceptance"]["proven"])
        entry["withdrawn_by_a_defect"] += bool(position["delivery"]["content_acceptance"]["withdrawn_by"])
    withdrawn = sorted({(p["company_id"], p["metric_id"], p["report_end"],
                         str(p["delivery"]["content_acceptance"]["withdrawn_by"]))
                        for p in frame["positions"]
                        if p["delivery"]["content_acceptance"]["withdrawn_by"]})

    snapshot = "requirements/issue_47_v1/baseline_manifest.json"
    manifests = {"repository": json.loads(subprocess.run(
                     ["git", "show", COMMIT + ":" + snapshot], cwd=str(REPO), check=True,
                     capture_output=True, text=True).stdout),
                 "runtime": json.loads(RUNTIME_MANIFEST.read_text())}
    now = json.loads((REPO / snapshot).read_text())
    current = now["new_rule_files"]
    batch_rules = manifests["repository"]["new_rule_files"]
    since = {"added": sorted(set(current) - set(batch_rules)),
             "removed": sorted(set(batch_rules) - set(current)),
             "changed": sorted(path for path in set(current) & set(batch_rules)
                               if current[path] != batch_rules[path])}
    # Inherited files the generation records by bytes move too, when the base
    # is merged: they are not rule files, but a Run executes them all the same.
    held, then = now["execution_authority"]["files"], manifests["repository"]["execution_authority"]["files"]
    inherited = {"added": sorted(set(held) - set(then) - set(current)),
                 "removed": sorted(set(then) - set(held) - set(batch_rules)),
                 "changed": sorted(path for path in set(held) & set(then)
                                   if path not in current and held[path] != then[path])}

    def leaves(value, prefix=""):
        if isinstance(value, dict):
            for key, item in value.items():
                yield from leaves(item, prefix + "/" + key)
        else:
            yield prefix, value
    left, right = dict(leaves(manifests["repository"])), dict(leaves(manifests["runtime"]))
    differing = sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))
    rule_leaves = [key for key in left if key.startswith("/new_rule_files/")]

    report = {
        "record_type": "ISSUE_47_NATIVE_RUN_BATCH", "production_authorized": False,
        "what_this_is": ("every metric with a route over the 41 periods whose target original is saved "
                         "after the first SEC acquisition, one period per worker and data root, one "
                         "read-only runtime tree, zero calls"),
        "requirement_closure_hash": closures,
        "batch_commit": COMMIT,
        "rule_files_changed_in_the_checkout_since_the_batch_commit": since,
        "inherited_authority_files_changed_in_the_checkout_since_the_batch_commit": inherited,
        "calls": {key: calls[key] for key in ("provider", "paid", "sec")},
        "batch": {"planned": len(planned), "attempted": len(rows), "failures": len(failed),
                  "per_period": per_period},
        "separate_process_read_back": {"frozen_runs": len(frozen), "read_back_identically": len(replayed),
                                       "not_read_back": [r["case"] + ":" + r["metric_id"] for r in frozen
                                                         if r not in replayed]},
        "failed_attempts_by_kind": {kind: [{"position": r["case"] + ":" + r["metric_id"],
                                            "error": r["error"]} for r in failed
                                           if _failure_kind(r) == kind]
                                    for kind in sorted({_failure_kind(r) for r in failed})},
        "failed_kind_meanings": FAILED_KINDS,
        "fixed_after_the_batch_commit": FIXED_AFTER,
        "ran_without_a_value": {"positions": len(no_value) - len(structural),
                                "structurally_not_applicable_rows": len(structural),
                                "by_kind": split,
                                "counts": {kind: sum(codes.values()) for kind, codes in split.items()}},
        "frame": {key: frame[key] for key in (
            "enumerated_positions", "status_counts", "first_blocking_reason_counts",
            "delivery_by_outcome", "delivery_layer_counts", "delivery_layer_unproven_reasons",
            "dimension_counts", "acceptance_reading_states", "run_receipts_read",
            "unreadable_run_directories", "rejected_attempt_records", "unreadable_attempt_artifacts",
            "wired_historical_metric_ids", "scope_answered_metric_ids",
            "structural_applicability_metric_ids", "periods_planned_on")},
        "per_period": {key: dict(sorted(counter.items()))
                       for key, counter in sorted(per_period_frame.items())},
        "withdrawn_by_a_confirmed_defect": [
            {"company_id": c, "metric_id": m, "report_end": e, "withdrawn_by": w}
            for c, m, e, w in withdrawn],
        "the_two_trees": {"differing_manifest_leaves": len(differing),
                          "differing_leaves": differing,
                          "new_rule_file_leaves_compared": len(rule_leaves),
                          "new_rule_file_leaves_differing": sum(1 for key in rule_leaves if key in differing)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "measured.json").write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    print(json.dumps({"attempted": len(rows), "failures": len(failed), "frozen": len(frozen),
                      "read_back": len(replayed), "closure": closures[0],
                      "layers": frame.get("delivery_layer_counts")}, indent=1))


if __name__ == "__main__":
    main()
