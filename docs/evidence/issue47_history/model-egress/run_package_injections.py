"""Show that the run package's request check refuses what it should, and that each of its checks bears weight.

``build_run_package.hold_to_the_approval`` compares the digests the package
rebuilt with the measurement and with the approval body. Rebuilding takes
minutes, so these cases give it the digests directly: the measured ones (the
sealed commit's three measurement files, which a dry-run build of the package
reproduced 35 for 35) and an approval body laid out by the proposal's own
grants. Each case states the outcome it must have - pass, or one named
refusal - and a different refusal counts as a wrong outcome, so a check that
only fails because a later one happens to fire is not credited.

Then each check in the function is broken in memory, one at a time (the edit
must hit exactly once and compile, or nothing runs), and some named case must
change outcome. Nothing is written but the result file; zero calls.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/model-egress/run_package_injections.py --sealed-commit <sha>
"""
import argparse
import copy
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "docs/evidence/issue47_history/model-egress"
BUILDER = HERE / "build_run_package.py"
OUT = HERE / "run-package-injections.json"


def _load(source=None):
    if source is None:
        spec = importlib.util.spec_from_file_location("issue47_run_package", BUILDER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    module = types.ModuleType("issue47_run_package_injected")
    module.__file__ = str(BUILDER)
    exec(compile(source, str(BUILDER), "exec"), module.__dict__)
    return module


def _measurements_are_the_sealed_ones(builder, sealed):
    for path in builder.MEASUREMENTS.values():
        held = subprocess.run(["git", "show", sealed + ":" + path], cwd=REPO, capture_output=True)
        if held.returncode != 0 or held.stdout != (REPO / path).read_bytes():
            raise SystemExit("THE_MEASUREMENT_IS_NOT_THE_SEALED_ONE:" + path)


def _body(recorded):
    """An approval body laid out as the proposal lays it out, from the measured digests."""
    spec = importlib.util.spec_from_file_location("issue47_proposal", HERE / "propose_model_allowance.py")
    proposal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proposal)
    named = {grant["grant"]: [] for grant in proposal.GRANTS}
    for key, digests in recorded.items():
        metric, company, end = key.split(":", 2)
        named[proposal._covering_grant(metric, company, end)].extend(digests)
    total = sum(len(digests) for digests in recorded.values())
    return {"maximum_additional_provider_paid_sec_calls": [total, total, 0],
            "transport": dict(proposal.TRANSPORT),
            "scope": {"grants": [{**grant, "request_digests": sorted(named[grant["grant"]])}
                                 for grant in proposal.GRANTS]}}


def _grant(body, name):
    return next(grant for grant in body["scope"]["grants"] if grant["grant"] == name)


def cases(recorded, body):
    """(name, computed, recorded, body, expected) - expected is "PASS" or a refusal code."""
    d04 = sorted(key for key in recorded if key.startswith("D04:"))
    e01 = sorted(key for key in recorded if key.startswith("E01:"))
    one_d04, other_d04 = d04[0], d04[1]
    changed_digest = "sha256:" + "0" * 64
    rows = [("control: the measured digests and the body laid out from them", recorded, recorded, body, "PASS")]

    computed = copy.deepcopy(recorded)
    computed[one_d04][0] = changed_digest
    # The body follows the rebuilt bytes, so only the measurement check can see it.
    follows = _body(computed)
    rows.append(("the package rebuilt one request other than measured, and the body names it",
                 computed, recorded, follows, "RUN_PACKAGE_REQUESTS_ARE_NOT_THE_MEASURED_ONES"))

    fewer = copy.deepcopy(body)
    grant = _grant(fewer, "D04_MARRIOTT_FY2023_FY2024")
    grant["request_digests"] = grant["request_digests"][1:]
    rows.append(("a grant names one request fewer than its positions send", recorded, recorded, fewer,
                 "RUN_PACKAGE_GRANT_NAMES_OTHER_REQUESTS"))

    more = copy.deepcopy(body)
    _grant(more, "D04_MARRIOTT_FY2023_FY2024")["request_digests"].append(recorded[e01[0]][0])
    rows.append(("a grant also names another grant's request", recorded, recorded, more,
                 "RUN_PACKAGE_GRANT_NAMES_OTHER_REQUESTS"))

    repeated = copy.deepcopy(body)
    grant = _grant(repeated, "D04_MARRIOTT_FY2023_FY2024")
    grant["request_digests"] = sorted(grant["request_digests"] + grant["request_digests"][:1])
    rows.append(("a grant names one of its requests twice", recorded, recorded, repeated,
                 "RUN_PACKAGE_GRANT_NAMES_OTHER_REQUESTS"))

    overlapping = copy.deepcopy(body)
    _grant(overlapping, "E01_FY2025_CALENDAR_WINDOWS")["metric_ids"] = ["D02", "E01"]
    rows.append(("two grants cover the same position", recorded, recorded, overlapping,
                 "RUN_PACKAGE_POSITION_NOT_IN_EXACTLY_ONE_GRANT"))

    uncovered = copy.deepcopy(body)
    _grant(uncovered, "D04_PARAMOUNT_PREDECESSOR_FY2024")["company_ids"] = ["pfizer"]
    rows.append(("no grant covers a position", recorded, recorded, uncovered,
                 "RUN_PACKAGE_POSITION_NOT_IN_EXACTLY_ONE_GRANT"))

    twice = copy.deepcopy(body)
    twice["scope"]["grants"].append(copy.deepcopy(_grant(body, "E01_MACYS_FY2025")))
    rows.append(("the body lists one grant twice", recorded, recorded, twice, "RUN_PACKAGE_GRANT_NAMED_TWICE"))

    shared = copy.deepcopy(recorded)
    shared[other_d04] = sorted(shared[other_d04][:-1] + [shared[one_d04][0]])
    rows.append(("two positions of one grant send the same request, and the body names it twice",
                 shared, shared, _body(shared), "RUN_PACKAGE_TWO_POSITIONS_SHARE_A_REQUEST"))

    cap = copy.deepcopy(body)
    total = sum(len(digests) for digests in recorded.values())
    cap["maximum_additional_provider_paid_sec_calls"] = [total + 1, total + 1, 0]
    rows.append(("the cap is not the number of requests", recorded, recorded, cap,
                 "RUN_PACKAGE_CAP_IS_NOT_THE_REQUESTS"))

    sec = copy.deepcopy(body)
    sec["maximum_additional_provider_paid_sec_calls"][2] = 1
    rows.append(("the cap carries an SEC call", recorded, recorded, sec, "RUN_PACKAGE_CAP_IS_NOT_THE_REQUESTS"))
    return rows


def outcome(builder, computed, recorded, body):
    try:
        builder.hold_to_the_approval(computed=copy.deepcopy(computed), recorded=copy.deepcopy(recorded),
                                     body=copy.deepcopy(body))
    except SystemExit as refusal:
        return str(refusal).split(":", 1)[0]
    except Exception as error:  # a broken check that crashes instead of refusing by name
        return "ERROR:" + type(error).__name__
    return "PASS"


INJECTIONS = [
    ("THE_MEASUREMENT_IS_NOT_CHECKED", "    if computed != recorded:\n", "    if False:\n"),
    ("A_POSITION_MAY_FALL_IN_TWO_GRANTS", "        if len(covering) != 1:\n", "        if not covering:\n"),
    ("A_POSITION_MAY_FALL_IN_NO_GRANT", "        if len(covering) != 1:\n", "        if len(covering) > 1:\n"),
    ("GRANTS_COMPARED_AS_SETS",
     "if sorted(grant[\"request_digests\"]) != sorted(named[grant[\"grant\"]])]",
     "if set(grant[\"request_digests\"]) != set(named[grant[\"grant\"]])]"),
    ("A_GRANT_LISTED_TWICE_IS_ACCEPTED", "    if len(named) != len(grants):\n", "    if False:\n"),
    ("SHARED_REQUESTS_ARE_ACCEPTED",
     "    if len({digest for digests in computed.values() for digest in digests}) != total:\n",
     "    if False:\n"),
    ("THE_CAP_IS_NOT_CHECKED",
     "    if body[\"maximum_additional_provider_paid_sec_calls\"] != [total, total, 0]:\n", "    if False:\n"),
    ("THE_CAP_MAY_CARRY_SEC_CALLS",
     "    if body[\"maximum_additional_provider_paid_sec_calls\"] != [total, total, 0]:\n",
     "    if body[\"maximum_additional_provider_paid_sec_calls\"][:2] != [total, total]:\n"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sealed-commit", required=True)
    arguments = parser.parse_args()
    builder = _load()
    _measurements_are_the_sealed_ones(builder, arguments.sealed_commit)
    recorded = builder._measured(REPO)
    body = _body(recorded)
    rows = cases(recorded, body)
    control = []
    for name, computed, held, approval, expected in rows:
        got = outcome(builder, computed, held, approval)
        control.append({"case": name, "expected": expected, "got": got})
        if got != expected:
            raise SystemExit("A_CASE_HAS_THE_WRONG_OUTCOME_ON_THE_UNCHANGED_CHECK: " + json.dumps(control[-1]))
    source = BUILDER.read_text(encoding="utf-8")
    injected = []
    for label, old, new in INJECTIONS:
        if source.count(old) != 1:
            raise SystemExit("AN_INJECTION_EDIT_DOES_NOT_HIT_EXACTLY_ONCE: " + label)
        changed = _load(source.replace(old, new))
        moved = [{"case": name, "expected": expected, "got": got}
                 for name, computed, held, approval, expected in rows
                 for got in [outcome(changed, computed, held, approval)] if got != expected]
        injected.append({"injection": label, "caught": bool(moved), "caught_by": moved})
    result = {"record_type": "ISSUE_47_RUN_PACKAGE_CHECK_INJECTIONS",
              "checks": "build_run_package.hold_to_the_approval",
              "sealed_commit_measurements": arguments.sealed_commit,
              "positions": len(recorded), "requests": sum(len(v) for v in recorded.values()),
              "control": control, "injections": injected,
              "all_caught": all(row["caught"] for row in injected), "calls": [0, 0, 0]}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"control": len(control), "caught": sum(row["caught"] for row in injected),
                      "injections": len(injected)}))
    return 0 if result["all_caught"] else 1


if __name__ == "__main__":
    sys.exit(main())
