"""Measure what registering a historical Requirement actually costs.

Purpose:
    Issue #47 needs a native Run whose Requirement is not ``issue_28_v13``.
    Statements about what that costs have been made on the Issue from reading
    the code; this measures them instead, in a copy of an installed data root,
    without touching the development checkout, Issue #28's workspace or any
    published package.

    Two byte checks exist and they are not the same check, which is the whole
    reason the cost was mis-stated:

    * a Requirement's ``new_rule_files`` are verified inside
      ``load_profile_requirement_snapshot``, against both the data root and the
      installed code root. Breaking these breaks installation itself.
    * a Requirement's ``execution_authority.files`` are verified by
      ``validate_execution_authority``, which runs only inside
      ``load_run_requirement_snapshot``. Breaking these breaks loading or
      creating a Run, and nothing else.

    An installed data root carries its own copies of the authority files, so it
    is checked against itself. That is measured here rather than assumed.

Call relationships:
    Developers and the Issue #47 evidence archive call this script. It reads an
    installed data root, copies it, and runs the copy in separate processes. It
    makes no SEC or model request and creates no Run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

# The seam, as the repository already builds it for issue_28_v14: one engine
# entry keyed by generation, and one branch keyed by the Run's own
# requirement_id. Neither file is in any Requirement's rule set.
SEAM_FILES = ("scripts/vnext/requirement_profile.py", "scripts/vnext/run_store.py")
REPORTED_FILES = (*SEAM_FILES, "scripts/vnext/normal_run_v3.py",
                  "scripts/vnext/requirements.py", "scripts/vnext/capacity_run.py",
                  "config/issue28_normal_results_v2.json")

PROBE = '''
import json, sys
from pathlib import Path
sys.path.insert(0, {scripts!r})
root = Path({root!r})
out = {{}}
from vnext.requirements import load_requirement_snapshot, load_run_requirement_snapshot


def attempt(name, call):
    try:
        call()
        out[name] = "OK"
    except Exception as error:                      # noqa: BLE001 - reporting
        out[name] = type(error).__name__ + ": " + str(error)[:120]


loaded = {{}}
for rid in ("issue_28_v11", "issue_28_v12", "issue_28_v13", "issue_28_v14"):
    def load(rid=rid):
        loaded[rid] = load_requirement_snapshot(snapshot_dir=root / "requirements" / rid)
    attempt("load_requirement_snapshot:" + rid, load)

# What a Run record carries is exactly this identity triple, so a Run of that
# Requirement is simulated from the Requirement itself rather than invented.
for rid in ("issue_28_v13", "issue_28_v14"):
    def run_load(rid=rid):
        requirement = loaded[rid]
        load_run_requirement_snapshot(
            repo_root=root, task_contract_bindings=[], requirement_id=rid,
            requirement_closure_hash=requirement["requirement_closure_hash"],
            requirement_hashes=requirement["hashes"],
            artifact_requirement_generation="EXPLICIT_REQUIREMENT_V1",
            record_type="SUCCESSOR_RUN")
    attempt("load_run_requirement_snapshot:" + rid, run_load)

binding_id = {binding!r}
if binding_id:
    from vnext.historical_package import replay_historical_inputs
    def replay():
        replay_historical_inputs(data_root=root, company_id={company!r},
                                 metric_id={metric!r}, binding_id=binding_id)
    attempt("replay_historical_inputs", replay)
print(json.dumps(out))
'''


def _probe(*, root: Path, binding_id, company_id, metric_id, scripts=None):
    """Run the probes against one root, with an explicit code root.

    Code root and data root are separate arguments because they are separate
    things, and conflating them is what the current design forbids: a data root
    that is also its own code root is refused by ``_external``. That refusal is
    reported as a measurement rather than worked around.
    """
    scripts = Path(scripts) if scripts is not None else root / "scripts"
    if binding_id and not (scripts / "vnext/historical_package.py").is_file():
        # This code root does not carry the historical layer, so the replay that
        # exists today runs the development checkout's code against the root.
        scripts = REPO_ROOT / "scripts"
    completed = subprocess.run(
        [sys.executable, "-c", PROBE.format(
            scripts=str(scripts), root=str(root), binding=binding_id,
            company=company_id, metric=metric_id)],
        capture_output=True, text=True, cwd=str(root.parent))
    if completed.returncode != 0:
        raise SystemExit("probe failed:\n" + completed.stderr[-3000:])
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _membership(root: Path):
    rows = {}
    for rid in ("issue_28_v13", "issue_28_v14"):
        baseline = json.loads((root / "requirements" / rid / "baseline_manifest.json").read_text())
        rows[rid] = (set(baseline["new_rule_files"]),
                     set(baseline["execution_authority"]["files"]))
    table = {}
    for relative in REPORTED_FILES:
        table[relative] = {
            rid: ("rule+authority" if relative in rules and relative in authority
                  else "rule only" if relative in rules
                  else "authority only" if relative in authority else "-")
            for rid, (rules, authority) in rows.items()}
    return table


def _apply_seam(root: Path):
    """Register one further engine generation and one further Run branch.

    The edits are the same shape the repository already uses for issue_28_v14:
    a generation key naming a module that is imported only when a snapshot asks
    for it, and an ``elif`` keyed on the Run's own requirement_id. They are
    applied to a copy; nothing writes into the development checkout.
    """
    profile = root / "scripts/vnext/requirement_profile.py"
    text = profile.read_text()
    anchor = '    "PROFILE_DRIVEN_V15": ".requirement_profile_v15",\n'
    if anchor not in text:
        raise SystemExit("the lazy engine registration convention is not present")
    profile.write_text(text.replace(
        anchor, anchor + '    "PROFILE_DRIVEN_V16": ".requirement_profile_v16",\n', 1))
    store = root / "scripts/vnext/run_store.py"
    text = store.read_text()
    branch = '''    elif manifest.get("requirement_id") == "issue_28_v12":
        from .normal_run_v2 import validate_normal_run_authority'''
    if branch not in text:
        raise SystemExit("the run authority dispatch is not where this expects it")
    store.write_text(text.replace(branch, '''    elif manifest.get("requirement_id") == "issue_47_v1":
        from .historical_run import validate_run_authority as validate_historical_run_authority
        validate_historical_run_authority(repo_root=repo_root, manifest=manifest,
            records=records, compiled_specs=compiled_specs)
''' + branch, 1))
    changed = [str(profile.relative_to(root)), str(store.relative_to(root))]
    # An installed data root carries only the files its Requirement's execution
    # authority names, which is why the historical layer is absent from it and
    # why today's replay runs the development checkout's code against the root.
    # A Requirement that named the historical layer would install it here, so
    # the copy is given it before the copy is measured.
    for source in sorted((REPO_ROOT / "scripts/vnext").glob("historical_*.py")):
        target = root / "scripts/vnext" / source.name
        if not target.exists():
            target.write_bytes(source.read_bytes())
            changed.append(str(target.relative_to(root)))
    for name in ("normal_history_catalog.py", "normal_period_selection.py"):
        source = REPO_ROOT / "scripts/vnext" / name
        target = root / "scripts/vnext" / name
        if not target.exists():
            target.write_bytes(source.read_bytes())
            changed.append(str(target.relative_to(root)))
    policy = root / "config/normal_period_selection_v1.json"
    if not policy.exists():
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_bytes((REPO_ROOT / "config/normal_period_selection_v1.json").read_bytes())
        changed.append(str(policy.relative_to(root)))
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True,
                        help="An installed historical data root to measure.")
    parser.add_argument("--work", type=Path, required=True,
                        help="A fresh external directory for the modified copy.")
    parser.add_argument("--binding-id", help="Replay this installed binding in both trees.")
    parser.add_argument("--company-id", help="Company of the binding above.")
    parser.add_argument("--metric-id", help="Metric of the binding above.")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    root = arguments.data_root.resolve()
    work = arguments.work.resolve()
    if work.exists():
        raise SystemExit("refusing to write into an existing directory: " + str(work))
    if root == REPO_ROOT or REPO_ROOT in root.parents or root in REPO_ROOT.parents:
        raise SystemExit("the measured data root must be outside the checkout")

    probe = dict(binding_id=arguments.binding_id, company_id=arguments.company_id,
                 metric_id=arguments.metric_id)
    before = _probe(root=root, **probe)
    work.mkdir(parents=True)
    variant = work / "with-seam"
    shutil.copytree(root, variant, symlinks=True)
    changed = _apply_seam(variant)
    # The compatibility question is the already-installed package read by the
    # changed runtime, so the code root moves and the data root does not.
    after = _probe(root=root, scripts=variant / "scripts", **probe)
    # And the same tree used as both, which the design refuses on purpose.
    self_contained = _probe(root=variant, scripts=variant / "scripts", **probe)
    unchanged = _probe(root=root, **probe)

    report = {"record_type": "REQUIREMENT_SEAM_MEASUREMENT", "schema_version": 1,
              "measured_data_root": str(root), "modified_copy": str(variant),
              "seam_files_changed": changed,
              "rule_and_authority_membership": _membership(root),
              "installed_package_under_its_own_runtime": before,
              "installed_package_under_the_changed_runtime": after,
              "changed_runtime_reading_itself_as_a_data_root": self_contained,
              "original_root_re_measured_afterwards": unchanged,
              "checkout_modified": False, "native_run_created": False,
              "calls": {"provider": 0, "paid": 0, "sec": 0},
              "production_authorized": False}
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(report, ensure_ascii=False, indent=1,
                                               sort_keys=True) + "\n", encoding="utf-8")
    print("rule and authority membership, from the data root's own manifests:")
    print("  %-44s %-16s %-16s" % ("file", "issue_28_v13", "issue_28_v14"))
    for relative, marks in report["rule_and_authority_membership"].items():
        print("  %-44s %-16s %-16s" % (relative, marks["issue_28_v13"], marks["issue_28_v14"]))
    print("\nchanged in the copy: " + ", ".join(changed))
    print("\nthe same installed package, read by two runtimes:")
    print("  %-44s %-30s %-30s" % ("probe", "its own runtime", "the changed runtime"))
    for name in sorted(set(before) | set(after)):
        print("  %-44s %-30s %-30s"
              % (name, before.get(name, "-")[:30], after.get(name, "-")[:30]))
    print("\nthe changed runtime asked to treat its own tree as the data root:")
    for name in sorted(self_contained):
        print("  %-44s %s" % (name, self_contained[name][:60]))
    print("\noriginal root, re-measured after the copy was changed:")
    for name in sorted(unchanged):
        print("  %-44s %s" % (name, unchanged[name][:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
