"""Compare the sealed parallel receipt with the sequential baseline, injection by injection.

The owner's contract change (Issue #47 comment 5870869079) accepts parallel
sealing when the same injections are caught by the same named cases as the
sequential run. The baseline is the 2026-09-28 sequential run's 66 rows
(``sequential-interrupted-2026-09-28.log``; the container restarted during the
67th) and the other 12 run one after another in one copy
(``sequential-completion-2026-09-28.json``). For every injection this compares
the outcome, the expected class's outcome, whether the whole suite had to run,
and the cases that caught it; the fields that only a parallel row has - which
copy ran it and how long it took - are not compared.

The runs were not in one tree, and a row comparison alone would not say
whether they could have been: the parallel verifier is itself a file the
receipt binds, and base merges move the generation's snapshot. So this also
computes, from the repository's history, what differs between the commit
each baseline part ran on and the sealing commit:

- among the receipt-bound files, only ``verify.py`` (the change from
  sequential to parallel) and the generation's snapshot may differ; any other
  bound file differing means the comparison would measure a code change, and
  it is refused;
- inside the snapshot, the recorded execution-authority files that differ are
  listed, with nothing else in the snapshot allowed to differ;
- the receipt must have been sealed on the named commit: every bound file the
  patches do not own must hash as that commit's blob.

The interrupted run's tree was deleted after the restart; the commit it is
compared from is the one whose content it was built from, which is a record,
not something this can re-derive.

    python3 docs/evidence/issue47_history/model-egress/compare_with_sequential.py <sealing commit> [<out.json>]

Exits 0 only if every check holds.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
COMPARED = ("outcome", "expected_class", "expected_class_outcome", "whole_suite_run", "first_caught_by")
SNAPSHOT = "requirements/issue_47_v1/baseline_manifest.json"
VERIFY = "docs/evidence/issue47_history/model-egress/verify.py"
PATCHES = ("docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch",
           "docs/evidence/issue47_history/model-egress/egress-registration.patch")
BASELINE = (
    ("sequential_interrupted", "33ee27d1",
     "tree deleted after the restart; built from this commit's content (the journal fix was "
     "committed after the run started)"),
    ("sequential_completion", "1a3071e5",
     "its copy matched the tree it was made from when made and after its last injection"))


def _git(*arguments):
    return subprocess.run(["git", *arguments], cwd=REPO, capture_output=True, check=True).stdout


def _authority_differences(earlier, later):
    """Recorded files that differ between two commits' snapshots, and whether anything else does."""
    first = json.loads(_git("show", earlier + ":" + SNAPSHOT))
    second = json.loads(_git("show", later + ":" + SNAPSHOT))
    files = [first["execution_authority"]["files"], second["execution_authority"]["files"]]
    listed = sorted(name for name in set(files[0]) | set(files[1])
                    if files[0].get(name) != files[1].get(name))
    rest = [key for key in set(first) | set(second)
            if key != "execution_authority" and first.get(key) != second.get(key)]
    rest += ["execution_authority." + key for key in set(first["execution_authority"])
             | set(second["execution_authority"])
             if key != "files" and first["execution_authority"].get(key)
             != second["execution_authority"].get(key)]
    return listed, sorted(rest)


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2
    sealed = _git("rev-parse", "--verify", sys.argv[1] + "^{commit}").decode().strip()
    receipt = json.loads((HERE / "offline-verification.json").read_text(encoding="utf-8"))
    interrupted = [json.loads(line) for line in
                   (HERE / "sequential-interrupted-2026-09-28.log").read_text().splitlines()
                   if line.startswith("{")]
    completion = json.loads((HERE / "sequential-completion-2026-09-28.json").read_text(encoding="utf-8"))
    baseline = interrupted + completion["rows"]
    parallel = receipt["fault_injections"]
    names = [row["id"] for row in parallel]
    problems = []

    # Sealed on the named commit: the bound files the patches leave alone hash as its blobs.
    owned = {SNAPSHOT}
    for patch in PATCHES:
        owned |= {line[len("+++ b/"):].strip() for line in _git("show", sealed + ":" + patch)
                  .decode().splitlines() if line.startswith("+++ b/")}
    sealed_on = {path: hashlib.sha256(_git("show", sealed + ":" + path)).hexdigest()
                 == entry["sha256"] for path, entry in receipt["bound_files"].items()
                 if path not in owned}
    if not sealed_on or not all(sealed_on.values()):
        problems.append("THE_RECEIPT_WAS_NOT_SEALED_ON_THIS_COMMIT:"
                        + ",".join(sorted(path for path, same in sealed_on.items() if not same)))

    trees = {}
    for part, commit, note in BASELINE:
        bound = sorted(set(_git("diff", "--name-only", commit, sealed, "--", *receipt["bound_files"])
                           .decode().split()))
        listed, rest = _authority_differences(commit, sealed)
        trees[part] = {"commit": commit, "note": note, "bound_files_that_differ": bound,
                       "recorded_files_that_differ_inside_the_snapshot": listed,
                       "anything_else_in_the_snapshot_that_differs": rest}
        if set(bound) - {VERIFY, SNAPSHOT}:
            problems.append("A_BOUND_FILE_OTHER_THAN_THE_VERIFIER_AND_SNAPSHOT_DIFFERS:" + part)
        if rest:
            problems.append("THE_SNAPSHOT_DIFFERS_BEYOND_ITS_RECORDED_FILES:" + part)
    completion_checks = {
        "the_completion_stopped_nowhere": completion.get("stop") is None,
        "its_copy_was_the_tree_when_made": completion.get("copy_was_the_tree_when_made") is True,
        "its_copy_was_the_tree_after_its_last_injection":
            completion.get("copy_was_the_tree_after_the_last_injection") is True}
    problems += [name for name, held in completion_checks.items() if not held]
    if not (receipt["checks"].get("suite_left_the_tree_as_found")
            and receipt["checks"].get("the_sealing_tree_is_unchanged_by_the_injections")):
        problems.append("THE_RECEIPT_DOES_NOT_PROVE_THE_SEALED_TREE_CAME_BACK")
    if sorted(names) != sorted(row["id"] for row in baseline) or len(set(names)) != len(names) \
            or len(baseline) != len({row["id"] for row in baseline}):
        problems.append("THE_TWO_SIDES_DO_NOT_HOLD_THE_SAME_INJECTIONS_ONCE_EACH")
    by_id = {row["id"]: row for row in baseline}
    rows = []
    for row in parallel:
        other = by_id.get(row["id"], {})
        differs = [field for field in COMPARED if row.get(field) != other.get(field)]
        rows.append({"id": row["id"], "same": not differs, "differs_in": differs,
                     "parallel_copy": row.get("copy"), "parallel_seconds": row.get("seconds"),
                     "first_caught_by": row.get("first_caught_by")})
        if differs:
            problems.append(row["id"] + ":" + ",".join(differs))
    report = {"record_type": "ISSUE_47_EGRESS_PARALLEL_VERSUS_SEQUENTIAL",
              "receipt_id": receipt["receipt_id"], "sealing_commit": sealed,
              "sealed_on_the_commit": sealed_on,
              "baseline": {"sequential_interrupted_rows": len(interrupted),
                           "sequential_completion_rows": len(completion["rows"]),
                           "completion_checks": completion_checks,
                           "completion_tree_unchanged_as_recorded": completion.get("tree_unchanged"),
                           "why_that_is_not_required": (
                               "the completion only read the verification tree (one manifest, one "
                               "copy); the first parallel seal ran its suite in that tree in the same "
                               "minute, and its fixtures were there when the completion looked last")},
              "trees": trees, "compared_fields": list(COMPARED), "rows": rows,
              "same": sum(1 for row in rows if row["same"]), "problems": problems,
              "accepted": not problems, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(text, encoding="utf-8")
    print(json.dumps({"same": report["same"], "of": len(parallel), "problems": problems}))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
