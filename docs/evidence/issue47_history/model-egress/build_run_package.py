"""Record the sealed model-call run package, and rebuild it in a container and check it.

The run package is the sealed commit, the registration patch and the egress
patch exactly as that commit holds them, and the generation's snapshot
re-minted over the patched tree. The offline verification's receipt binds the
files the call path runs (the call modules, the patched boundary files, the
egress patch, the verification harness and its tests, and the minted
snapshot, which records every rule file's bytes); the live path re-checks
those bindings before any socket (``historical_model_calls.verify_model_wiring``).

Real calls run in a session that holds the provider key, and the key reaches a
session only when it starts: a new session is a new container. So the package
is rebuilt there instead of carried, and every file the receipt binds must come
out byte-identical, or this refuses before anything else runs. Then the
package's own code rebuilds every request the approval names, with no call:
each measured position's ledger digests must equal the measurement, and each
grant must name exactly the digests of the positions it covers, adding up to
the cap. A claim computes the same digest and refuses one no grant names, so a
package that rebuilt other request bytes would otherwise stop at its first
claim, after the owner had approved and the key had been issued. Each request's
body is also counted with the pinned reference tokenizer and must weigh what
was measured: the live path stops the allowance when the service's count is
not that count, and the tokenizer is a dependency of the container, not of the
commit (requirements-continuous-context.txt, pinned in run-package.json).
Development
commits after the sealed one never enter the package's code. Three kinds of
file come from the checkout instead, because they are written after the seal
and do not change what runs:

* the receipt itself and the approval body the owner posts, each pinned by
  digest in run-package.json (the approval names the receipt; the receipt's
  bound files are checked here and again by the live path);
* this generation's model-call registration, once committed (the allowance,
  the approval record, the granted-ledger record): the gate re-reads the
  approval from GitHub before it accepts them;
* every committed model-ledger export (evidence/issue47_model_calls/): with
  them a start refuses an approval the branch already exported, and a ledger
  behind its export is refused (historical_ledger_start). A package built
  without them would lose that guard.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/model-egress/build_run_package.py record \
        --sealed-commit <sha>       write run-package.json, then build it once in
                                    a scratch directory to show it holds
    python3 docs/evidence/issue47_history/model-egress/build_run_package.py build <new directory>

Zero calls. ``record`` writes run-package.json; ``build`` writes only the new
directory (it may fetch the sealed commit if a shallow checkout lacks it).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = "docs/evidence/issue47_history/model-egress/"
RECORD = HERE + "run-package.json"
RECEIPT = HERE + "offline-verification.json"
APPROVAL_BODY = HERE + "approval-comment-body.json"
REGISTRATION_PATCH = "docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch"
EGRESS_PATCH = HERE + "egress-registration.patch"
# Written by register-approval and committed afterwards; carried when present.
REGISTRATION_OUTPUTS = ("config/issue47_historical_model_calls_v1.json",
                        HERE + "approval-comment.json",
                        HERE + "granted-model-ledger.json")
EXPORTS = "evidence/issue47_model_calls"
# The three measurements the approval's cap and digests were read from, as the
# sealed commit holds them (propose_model_allowance.py reads the same three).
MEASUREMENTS = {"D04": HERE + "d04-request-measurement.json",
                "E01": "docs/evidence/issue47_history/e01-content-confirmed/request-measurement.json",
                "D02": "docs/evidence/issue47_history/d02-item-8-review/request-measurement.json"}
# What each measured request's body weighed, compared request by request.
COUNTED = ("provider_body_bytes", "reference_input_tokens")
# The dependency the reference count needs (continuous_request_context pins its
# version and its tokenizer file); a package without it refuses before a claim.
TOKENIZER_REQUIREMENT = "requirements-continuous-context.txt"
# Run inside the built package, by the package's own code: every measured
# position's ledger digests under the approved transport, with the functions a
# claim uses (historical_model_calls.planned_request_digests), and each digested
# request's body counted with the pinned reference tokenizer the live path
# compares the service's count with. Nothing is sent.
DIGESTS_IN_THE_PACKAGE = r"""
import json
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from vnext import historical_model_calls as calls
from vnext.continuous_request_context import measure_request
from vnext.continuous_semantic_calls import request_body
from vnext.normal_period_selection import resolve_period_selection
root = Path.cwd().resolve()
if Path(calls.__file__).resolve().parents[2] != root:
    raise SystemExit("RUN_PACKAGE_CODE_IS_NOT_THE_PACKAGES:" + calls.__file__)
transport = json.loads(sys.argv[1])
# Each request the claim path's own function digests, held as it digests it.
digested = []
digest_of = calls.ledger_digest
def holding(request, policy):
    digest = digest_of(request, policy)
    digested.append((digest, request, policy))
    return digest
calls.ledger_digest = holding
digests, counts = {}, {}
for metric, company, end in json.loads(sys.argv[2]):
    key = metric + ":" + company + ":" + end
    selection = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
    del digested[:]
    returned = calls.planned_request_digests(
        company_id=company, metric_id=metric, period_selection=selection, transport=transport,
        data_root=root)
    if [digest for digest, _, _ in digested] != list(returned):
        raise SystemExit("RUN_PACKAGE_DIGESTED_REQUESTS_ARE_NOT_THE_RETURNED_ONES:" + key)
    digests[key] = sorted(returned)
    counts[key] = {}
    for digest, request, policy in digested:
        body = request_body(request, policy)
        counts[key][digest] = {"provider_body_bytes": len(body), "reference_input_tokens": measure_request(
            body, require_reference=True)["input_tokens"]}
print(json.dumps({"digests": digests, "counts": counts}, sort_keys=True))
"""


def _sha(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def _run(arguments, cwd):
    done = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit("RUN_PACKAGE_STEP_FAILED: " + " ".join(arguments) + "\n" + done.stderr[-2000:])
    return done.stdout


def _committed(commit, relative):
    done = subprocess.run(["git", "show", commit + ":" + relative], cwd=REPO, capture_output=True)
    if done.returncode != 0:
        raise SystemExit("RUN_PACKAGE_SEALED_COMMIT_LACKS: " + relative)
    return done.stdout


def _have_commit(commit):
    if subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=REPO,
                      capture_output=True).returncode == 0:
        return
    # A shallow checkout of a later branch tip may not reach the sealed commit.
    _run(["git", "fetch", "-q", "--no-tags", "origin", commit], cwd=REPO)
    if subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=REPO,
                      capture_output=True).returncode != 0:
        raise SystemExit("RUN_PACKAGE_SEALED_COMMIT_UNREACHABLE: " + commit)


def _measured_rows(target):
    """Every measured position's request rows, read as the proposal reads them."""
    read = {metric: json.loads((target / path).read_text(encoding="utf-8"))
            for metric, path in MEASUREMENTS.items()}
    rows = {}
    for key, row in read["D04"]["positions"].items():
        rows["D04:" + key] = row["requests"]
    for row in read["E01"]["windows"]:
        if "request_id" in row:
            rows["E01:" + row["company_id"] + ":" + row["report_end"]] = [row]
    for row in read["D02"]["positions"]:
        rows["D02:" + row["company_id"] + ":" + row["report_end"]] = [row]
    return rows


def _measured(target):
    """Every measured position's recorded digests."""
    return {key: sorted(row["ledger_digest"] for row in rows)
            for key, rows in _measured_rows(target).items()}


def _measured_counts(target):
    """Every measured request's body bytes and reference input tokens, by digest."""
    return {key: {row["ledger_digest"]: {name: row[name] for name in COUNTED} for row in rows}
            for key, rows in _measured_rows(target).items()}


def reproduce_requests(target, body):
    """Recompute, in the package, every request the approval names; refuse unless they are the same.

    The live path computes a claim's digest from the pinned filing and refuses
    one no grant names, so a package that rebuilt other request bytes than the
    sealed tree did would stop at its first claim. This asks the package's own
    code first, with no call (hold_to_the_approval says what must agree).
    """
    recorded = _measured(target)
    positions = sorted(key.split(":", 2) for key in recorded)
    with tempfile.TemporaryDirectory() as cache:
        done = subprocess.run(
            [sys.executable, "-c", DIGESTS_IN_THE_PACKAGE, json.dumps(body["transport"]),
             json.dumps(positions)], cwd=target, capture_output=True, text=True,
            env={**os.environ, "PYTHONPYCACHEPREFIX": cache, "PYTHONDONTWRITEBYTECODE": "1"})
    if done.returncode != 0 and "CONTINUOUS_CONTEXT_REFERENCE_REQUIRED" in done.stderr:
        # The live path would refuse the same way before a claim; here it is
        # found before the key is used, with what fixes it.
        raise SystemExit("RUN_PACKAGE_REFERENCE_TOKENIZER_UNAVAILABLE: python3 -m pip install "
                         "--require-hashes -r " + TOKENIZER_REQUIREMENT + "\n" + done.stderr[-600:])
    if done.returncode != 0:
        raise SystemExit("RUN_PACKAGE_REQUESTS_NOT_REBUILT:\n" + done.stderr[-2000:])
    computed = json.loads(done.stdout.strip().splitlines()[-1])
    held = hold_to_the_approval(computed=computed["digests"], recorded=recorded, body=body)
    held["reference_counts"] = hold_to_the_counts(computed=computed["counts"],
                                                  recorded=_measured_counts(target))
    return held


def hold_to_the_counts(*, computed, recorded):
    """Each rebuilt request's body bytes and reference input tokens against the measurement.

    The live path stops the whole allowance when the service's input count is
    not the pinned reference tokenizer's count for the body it sent
    (CONTEXT_REFERENCE_MISMATCH), after that call is paid. The package counts
    every approved request with the same tokenizer before any claim: a missing
    or other-version tokenizer refuses in the package (measure_request requires
    the pinned one), and a count other than the measured one refuses here.
    """
    moved = sorted(key for key in set(computed) | set(recorded) if computed.get(key) != recorded.get(key))
    if moved:
        raise SystemExit("RUN_PACKAGE_REFERENCE_COUNTS_ARE_NOT_THE_MEASURED_ONES: " + ",".join(moved))
    return {"requests": sum(len(requests) for requests in computed.values()),
            "reference_input_tokens": sum(row["reference_input_tokens"] for requests in computed.values()
                                          for row in requests.values())}


def hold_to_the_approval(*, computed, recorded, body):
    """The rebuilt digests against the measurement and the approval; a summary, or a named refusal.

    Each measured position's digests must equal what was measured, each
    position must fall in exactly one grant, the digests a grant names must be
    exactly those of the positions it covers (no more, no fewer, no repeats),
    and they must add up to the approved cap, with no SEC call in it.
    """
    if computed != recorded:
        raise SystemExit("RUN_PACKAGE_REQUESTS_ARE_NOT_THE_MEASURED_ONES: " + ",".join(
            sorted(key for key in set(computed) | set(recorded) if computed.get(key) != recorded.get(key))))
    grants = body["scope"]["grants"]
    named = {grant["grant"]: [] for grant in grants}
    if len(named) != len(grants):
        raise SystemExit("RUN_PACKAGE_GRANT_NAMED_TWICE")
    for key, digests in computed.items():
        metric, company, end = key.split(":", 2)
        covering = [grant["grant"] for grant in grants
                    if metric in grant["metric_ids"] and company in grant["company_ids"]
                    and grant["earliest_report_end"] <= end <= grant["latest_report_end"]]
        if len(covering) != 1:
            raise SystemExit("RUN_PACKAGE_POSITION_NOT_IN_EXACTLY_ONE_GRANT: " + key)
        named[covering[0]].extend(digests)
    differs = [grant["grant"] for grant in grants
               if sorted(grant["request_digests"]) != sorted(named[grant["grant"]])]
    if differs:
        raise SystemExit("RUN_PACKAGE_GRANT_NAMES_OTHER_REQUESTS: " + ",".join(differs))
    total = sum(len(digests) for digests in computed.values())
    if len({digest for digests in computed.values() for digest in digests}) != total:
        raise SystemExit("RUN_PACKAGE_TWO_POSITIONS_SHARE_A_REQUEST")
    if body["maximum_additional_provider_paid_sec_calls"] != [total, total, 0]:
        raise SystemExit("RUN_PACKAGE_CAP_IS_NOT_THE_REQUESTS")
    return {"positions": len(computed), "requests": total,
            "by_metric": {metric: sum(len(digests) for key, digests in computed.items()
                                      if key.startswith(metric + ":")) for metric in MEASUREMENTS}}


def record(sealed_commit):
    """Write run-package.json from the sealed commit and the committed receipt and approval body."""
    sealed_commit = _run(["git", "rev-parse", "--verify", sealed_commit + "^{commit}"], cwd=REPO).strip()
    receipt_raw = (REPO / RECEIPT).read_bytes()
    receipt = json.loads(receipt_raw)
    if receipt.get("all_checks_passed") is not True:
        raise SystemExit("RUN_PACKAGE_RECEIPT_DID_NOT_PASS")
    body_raw = (REPO / APPROVAL_BODY).read_bytes()
    body = json.loads(body_raw)
    if body.get("model_wiring_receipt_id") != receipt["receipt_id"]:
        raise SystemExit("RUN_PACKAGE_APPROVAL_NAMES_ANOTHER_RECEIPT")
    value = {"record_type": "ISSUE_47_MODEL_CALL_RUN_PACKAGE", "schema_version": 1,
             "sealed_commit": sealed_commit,
             "registration_patch": {"path": REGISTRATION_PATCH,
                                    **_sha(_committed(sealed_commit, REGISTRATION_PATCH))},
             "egress_patch": {"path": EGRESS_PATCH, **_sha(_committed(sealed_commit, EGRESS_PATCH))},
             "tokenizer_requirement": {"path": TOKENIZER_REQUIREMENT,
                                       **_sha(_committed(sealed_commit, TOKENIZER_REQUIREMENT))},
             "receipt_id": receipt["receipt_id"], "receipt": {"path": RECEIPT, **_sha(receipt_raw)},
             "approval_body": {"path": APPROVAL_BODY, **_sha(body_raw)},
             "bound_files": len(receipt["bound_files"]),
             "carried_from_the_checkout": [RECEIPT, APPROVAL_BODY, *REGISTRATION_OUTPUTS, EXPORTS + "/"],
             "calls": [0, 0, 0]}
    (REPO / RECORD).write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory() as scratch:
        built = build(Path(scratch) / "package")
    return {"status": "RUN_PACKAGE_RECORDED", "record": RECORD, "checked_by_building": built}


def build(target):
    """Rebuild the package in ``target`` and check every bound file against the receipt."""
    package = json.loads((REPO / RECORD).read_text(encoding="utf-8"))
    receipt_raw = (REPO / RECEIPT).read_bytes()
    body_raw = (REPO / APPROVAL_BODY).read_bytes()
    if {"path": RECEIPT, **_sha(receipt_raw)} != package["receipt"]:
        raise SystemExit("RUN_PACKAGE_RECEIPT_IS_NOT_THE_RECORDED_ONE")
    if {"path": APPROVAL_BODY, **_sha(body_raw)} != package["approval_body"]:
        raise SystemExit("RUN_PACKAGE_APPROVAL_BODY_IS_NOT_THE_RECORDED_ONE")
    receipt = json.loads(receipt_raw)
    target = Path(target).resolve()
    if target.exists():
        raise SystemExit("RUN_PACKAGE_TARGET_EXISTS: " + str(target))
    _have_commit(package["sealed_commit"])
    _run(["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(target)], cwd=REPO)
    _run(["git", "checkout", "-q", "--detach", package["sealed_commit"]], cwd=target)
    for key in ("registration_patch", "egress_patch"):
        relative = package[key]["path"]
        if {"path": relative, **_sha((target / relative).read_bytes())} != package[key]:
            raise SystemExit("RUN_PACKAGE_PATCH_DIFFERS: " + relative)
        _run(["git", "apply", relative], cwd=target)
    _run([sys.executable, "tools/vnext_mint_historical_requirement.py"], cwd=target)
    _run([sys.executable, "tools/vnext_mint_historical_requirement.py", "--check"], cwd=target)
    (target / RECEIPT).write_bytes(receipt_raw)
    (target / APPROVAL_BODY).write_bytes(body_raw)
    carried = [RECEIPT, APPROVAL_BODY]
    for relative in REGISTRATION_OUTPUTS:
        if (REPO / relative).is_file():
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            (target / relative).write_bytes((REPO / relative).read_bytes())
            carried.append(relative)
    if (REPO / EXPORTS).is_dir():
        if (target / EXPORTS).exists():
            shutil.rmtree(target / EXPORTS)
        shutil.copytree(REPO / EXPORTS, target / EXPORTS, symlinks=True)
        carried.append(EXPORTS + "/")
    for relative, binding in sorted(receipt["bound_files"].items()):
        path = target / relative
        if not path.is_file() or path.is_symlink() or _sha(path.read_bytes()) != binding:
            raise SystemExit("RUN_PACKAGE_FILE_DIFFERS_FROM_THE_RECEIPT: " + relative)
    reproduced = reproduce_requests(target, json.loads(body_raw))
    return {"status": "RUN_PACKAGE_BUILT", "target": str(target),
            "sealed_commit": package["sealed_commit"], "receipt_id": receipt["receipt_id"],
            "bound_files_checked": len(receipt["bound_files"]), "carried": carried,
            "approved_requests_rebuilt_in_the_package": reproduced, "calls": [0, 0, 0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("record")
    write.add_argument("--sealed-commit", required=True)
    make = commands.add_parser("build")
    make.add_argument("target", type=Path)
    arguments = parser.parse_args()
    result = (record(arguments.sealed_commit) if arguments.command == "record"
              else build(arguments.target))
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
