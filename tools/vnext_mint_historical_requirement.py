"""Mint the issue_47_v1 Requirement snapshot from the current tree.

Purpose:
    A Requirement snapshot is content: parent identity, the rule files this
    generation adds, and the execution authority its Runs are validated
    against. Writing those hashes by hand is how they drift, so this mints them
    from the files themselves and refuses to write anything it cannot read.

    Producing the snapshot grants nothing. It creates no Run, makes no request,
    and does not register the engine - registration is a separate change to two
    files that are inside issue_28_v13's execution authority, delivered as a
    patch under docs/evidence/issue47_history/.

Call relationships:
    Developers call this. It reads requirements/issue_28_v13, the historical
    layer's own files, and writes requirements/issue_47_v1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vnext.canonical import sha256_file  # noqa: E402
from vnext.requirements import load_requirement_snapshot  # noqa: E402

REQUIREMENT_ID = "issue_47_v1"
PARENT_ID = "issue_28_v13"
SNAPSHOT_FILES = ("CONTRACT.md", "baseline_manifest.json", "decision_register.json",
                  "invariant_profile.json", "transfer_manifest.json")

# What this generation adds over its parent: the historical layer's own code and
# its selection policy. Everything else is the parent's and stays the parent's.
NEW_RULE_FILES = (
    "config/normal_period_selection_v1.json",
    "scripts/vnext/normal_history_catalog.py",
    "scripts/vnext/normal_history_plan.py",
    "scripts/vnext/normal_period_selection.py",
    "scripts/vnext/historical_annual_input.py",
    "scripts/vnext/historical_results.py",
    # A D02 Run executes this, and neither the rule set nor the inherited
    # authority named it. It was missed because historical_run and
    # historical_results both import it inside a function, and the import
    # closure tool walks module-scope imports only.
    "scripts/vnext/historical_text_input.py",
    "scripts/vnext/historical_zero_ai_results.py",
    "scripts/vnext/historical_accession_results.py",
    "scripts/vnext/historical_package.py",
    "scripts/vnext/historical_run.py",
    "scripts/vnext/historical_projection.py",
    # Added when a Pfizer D02 Result that passed every check turned out to hold
    # another item's text. The repair belongs in text_coverage, whose bytes
    # issue_28_v11 names, so this generation carries it as its own rule file.
    "scripts/vnext/historical_text_results.py",
    # The D02 Spec revision and the module that compiles it. A file whose bytes
    # decide a metric's bound belongs in the rule set rather than only in the
    # authority, so both roots check it.
    "catalog/r6/D02_legal_disclosures_v2.md",
    "scripts/vnext/historical_spec_revision.py",
    # 64 was two bounds: what a Spec may declare, and what ORDERED_NEWLINE_V1
    # will render. This carries the second, so a file that decides how many
    # excerpts a result may hold is checked on both roots.
    "scripts/vnext/historical_text_protocol.py",
    "scripts/vnext/requirement_profile_v16.py",
)

# One module the parent's authority does not name although its own named code
# imports it at module scope. scripts/vnext/requirement_profile.py is in the
# authority and begins by importing requirement_profile_v10 through v14; v11 is
# the only one of the five missing from the list. The consequence is not
# cosmetic: a delivery assembled strictly from the execution authority cannot
# import requirement_profile, so it cannot load any Requirement and cannot
# replay any Run. Measured by walking the module-scope import graph from the
# 182 Python modules the authority names - the closure is 183, and this is the
# one file in the difference.
#
# issue_28_v13's own manifest is not touched. A Requirement names the code its
# own Runs execute, and this one does.
AUTHORITY_ADDITIONS = ("scripts/vnext/requirement_profile_v11.py",)

# Three files the parent already binds, whose bytes a historical Run needs to be
# the registered ones rather than the pre-registration ones: the engine registry,
# the Run authority dispatch, and the record semantics that decide whether a
# fiscal label may sit in the calendar year before an instant's own. They are NOT re-signed in the parent - the
# parent's manifest is untouched and its closure hash is unchanged. This
# successor records what its own Runs execute, which is what an execution
# authority is for. The consequence is stated rather than hidden: one data root
# satisfies issue_28_v13 or issue_47_v1, not both, because the two manifests
# require different bytes for these two files.
RE_RECORDED_FROM_TREE = (
    "scripts/vnext/requirement_profile.py",
    "scripts/vnext/run_store.py",
    # Added after a non-calendar fiscal year proved it necessary. Macy's fiscal
    # 2025 ends 2026-01-31, so an instant measured at that period end carries
    # fiscal_year 2025 with period_end.year 2026. validate_run_coordinates
    # allows that only under point_in_time_fiscal_label, which both run_store
    # and records decide from their own hard-coded set of requirement ids. Both
    # sets had to learn issue_47_v1, and records.py is bound by the parent, so
    # its patched bytes have to be recorded here too.
    "scripts/vnext/records.py",
    # Wiring the successor protocol means the registration patch now edits
    # three more files that issue_28_v13 already records, so their patched
    # bytes have to be recorded here too. This makes the divergence between
    # this generation and its parent WIDER - six files rather than three - and
    # that is the actual cost of the capacity change, recorded rather than
    # described as an isolation benefit.
    "scripts/vnext/calculator.py",
    "scripts/vnext/constraints.py",
    "scripts/vnext/projector.py",
)

CONTRACT = """# Historical pinned-period development successor

This UNFROZEN development successor to `issue_28_v13` adds one capability: a
Run whose annual period is an explicit, proven selection rather than whatever
the latest saved filing happens to be. The parent's ten companies, 39 metrics
and every obligation it carries are inherited unchanged through its own engine,
which re-checks its own rule bytes on both roots.

What this generation binds in addition is the historical layer itself: the
saved-submissions catalog reader, the acquisition planner, the period
selection policy and selector, the pinned-period annual input, the three thin
source adapters, the pinned-period text input, the package installer and the
historical Run wiring. A Run that declares this Requirement therefore records
an execution authority that names the code that produced it.

It also binds one correction to inherited behaviour. A numbered Form 10-K item
ends at the next numbered heading, and an omitted item is allowed to be closed
by a later number; Form 10-K separately lets a registrant carry the executive
officer information as an unnumbered item inside Part I. Where both apply the
numbered item absorbs the unnumbered one, and this generation's text route
closes it at that boundary instead. The correction is the historical route's
only. The inherited route keeps the behaviour its own frozen bytes describe,
because the file that decides it is named by `issue_28_v11`'s rule set.

First-report semantics are unchanged: the current value comes from the current
selected filing and the prior value from the prior selected filing. No
latest-restated or point-in-time view is authorized. Metrics without a
historical route return an explicit implementation gap; they never fall back to
the latest period and are never reported as absent disclosure.

Old frozen snapshots, engines, new_rule_files and source records remain
immutable. No provider, paid or SEC budget, no activation, adoption, merge,
deployment or active switch is granted by this Requirement. Frozen development
results and full acceptance have not been produced by this draft.
"""

INVARIANTS = {
    "installed_profile_and_rules_exact": True,
    "native_source_replay_before_acceptance": True,
    "actual_measurement_period_preserved": True,
    "selected_period_is_proven_not_supplied": True,
    "current_and_prior_each_from_its_own_filing": True,
    "issuer_fiscal_label_read_from_full_primary_document": True,
    "latest_restated_view_not_authorized": True,
    "unwired_route_reported_as_implementation_gap": True,
    "production_authorized": False,
}


def _binding(relative: str) -> dict:
    path = REPO_ROOT / relative
    if not path.is_file():
        raise SystemExit("missing rule file: " + relative)
    return {"sha256": sha256_file(path=path), "size": path.stat().st_size}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Fail if the minted snapshot differs from what is on disk.")
    arguments = parser.parse_args(argv)

    parent = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements" / PARENT_ID)
    parent_baseline = json.loads(
        (REPO_ROOT / "requirements" / PARENT_ID / "baseline_manifest.json").read_text())

    # The execution authority is the parent's, plus the historical files a Run
    # of this generation actually executes. Nothing is dropped from it.
    authority = dict(parent_baseline["execution_authority"]["files"])
    for relative in NEW_RULE_FILES + AUTHORITY_ADDITIONS:
        authority[relative] = _binding(relative)
    diverged = []
    for relative in RE_RECORDED_FROM_TREE:
        current = _binding(relative)
        if authority.get(relative) != current:
            diverged.append(relative)
        authority[relative] = current

    policy = json.loads((REPO_ROOT / "config/normal_period_selection_v1.json").read_text())
    parent_policy = json.loads(
        (REPO_ROOT / "config/issue28_normal_results_v2.json").read_text())

    baseline = {
        "schema_version": 1,
        "record_type": "REQUIREMENT_BASELINE_MANIFEST",
        "requirement_id": REQUIREMENT_ID,
        "requirement_generation": "PROFILE_DRIVEN_V16",
        "artifact_requirement_generation": "EXPLICIT_REQUIREMENT_V1",
        "contract_revision": "historical-pinned-period-v1",
        "parent": {
            "requirement_id": PARENT_ID,
            "requirement_closure_hash": parent["requirement_closure_hash"],
            "snapshot_files": {
                name: {"sha256": sha256_file(
                           path=REPO_ROOT / "requirements" / PARENT_ID / name),
                       "size": (REPO_ROOT / "requirements" / PARENT_ID / name).stat().st_size}
                for name in SNAPSHOT_FILES},
        },
        "validator": {
            "path": "scripts/vnext/requirement_profile_v16.py",
            **_binding("scripts/vnext/requirement_profile_v16.py"),
            "dependencies": ["scripts/vnext/requirement_profile_v1.py",
                             "scripts/vnext/canonical.py",
                             "scripts/vnext/sources.py"],
        },
        "new_rule_files": {relative: _binding(relative) for relative in sorted(NEW_RULE_FILES)},
        "execution_authority": {
            "files": dict(sorted(authority.items())),
            "semantic_runtime_versions_hash":
                parent_baseline["execution_authority"]["semantic_runtime_versions_hash"],
        },
    }
    files = {
        "CONTRACT.md": CONTRACT,
        "baseline_manifest.json": json.dumps(baseline, ensure_ascii=False, indent=1,
                                             sort_keys=True) + "\n",
        "decision_register.json": json.dumps(
            {"status": "USER_DELEGATED_DEVELOPMENT_ONLY", "policy": policy,
             "inherited_policy": parent_policy},
            ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        "invariant_profile.json": json.dumps(INVARIANTS, ensure_ascii=False, indent=1,
                                             sort_keys=True) + "\n",
        "transfer_manifest.json": json.dumps(
            {"parent_requirement_id": PARENT_ID,
             "parent_requirement_closure_hash": parent["requirement_closure_hash"],
             "disposition": "CARRY_ALL_PARENT_OBLIGATIONS_WITHOUT_ACTIVATION",
             "pending_decision_ids": parent["pending_decision_ids"]},
            ensure_ascii=False, indent=1, sort_keys=True) + "\n",
    }
    directory = REPO_ROOT / "requirements" / REQUIREMENT_ID
    if arguments.check:
        differing = [name for name, text in files.items()
                     if not (directory / name).is_file()
                     or (directory / name).read_text() != text]
        if differing:
            raise SystemExit("minted snapshot differs from disk: " + ", ".join(sorted(differing)))
        print("issue_47_v1 snapshot matches the current tree")
        return 0
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (directory / name).write_text(text, encoding="utf-8")
    print("wrote requirements/%s: %d rule files, %d authority files"
          % (REQUIREMENT_ID, len(baseline["new_rule_files"]),
             len(baseline["execution_authority"]["files"])))
    print("parent closure (unchanged by this):", parent["requirement_closure_hash"])
    if diverged:
        print("re-recorded from this tree, so they differ from what %s records:" % PARENT_ID)
        for relative in diverged:
            print("   " + relative)
        print("a data root therefore satisfies one of the two Requirements, not both")
    else:
        print("no inherited authority entry differs from %s" % PARENT_ID)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
