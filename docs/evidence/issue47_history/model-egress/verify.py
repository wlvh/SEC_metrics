"""Verify Issue #47's model-egress patch offline, in a tree where it is applied, and seal the result.

Run from the root of a runtime tree that carries the issue_47_v1 registration
patch, after applying this directory's egress-registration.patch and minting:

    git apply docs/evidence/issue47_history/model-egress/egress-registration.patch
    python3 tools/vnext_mint_historical_requirement.py
    python3 docs/evidence/issue47_history/model-egress/verify.py

It never runs in the repository checkout: the patch is not applied there, and
the controller refuses issue_47_v1 there (which the repository's own
tests/vnext/test_historical_model_calls.py asserts). Steps, each recorded:

1. the patch is the one applied here (``git apply -R --check``) and the
   snapshot is minted for these bytes;
2. the repository's egress gate passes and names the one new caller;
3. the verification suite passes (every case, network refused);
4. every fault injection is caught, and by which case. Each injection names
   the class written to catch it; that class runs first, fail-fast, and a
   failing case there is recorded as the catch. Only when it does not catch
   does the whole suite run, fail-fast in the fixed order, so a catch
   elsewhere is still found and recorded as elsewhere. (The first versions
   ran the whole suite for every injection; at 45 injections and 58 cases
   that is most of a day, and it answers no more: a catch is a catch whichever
   case makes it, and the expected class is named so a reader can check the
   case is the one designed for it. ``first_caught_by`` is not the full set of
   catching cases either way.)
   Two ways an injection can look caught without any case having seen it are
   closed. Injected text must compile: a syntax error fails the suite before
   one case runs. And an injection into a file the snapshot records by bytes
   is minted before the suite runs, because the byte binding refuses every
   change, harmless or not - a catch there says the file is bound, not that a
   case asserts the property the injection breaks. The file is restored and
   minted again afterwards, and the snapshot must come back byte for byte.
   A catch in a class fixture is recorded as one, with what it raised;
5. which frozen generations record the three boundary files, and so would be
   moved by applying the patch - measured from their manifests, not assumed;
6. the tree is back where it started: the patch still applies in reverse, the
   snapshot still matches, and every bound file has the bytes it had before.

Only if all of that holds is ``offline-verification.json`` sealed. Zero calls.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
HERE = "docs/evidence/issue47_history/model-egress"
PATCH = HERE + "/egress-registration.patch"
OUTPUT = HERE + "/offline-verification.json"
SUITE = "tests.vnext.test_historical_model_egress"
# Fast classes first, so fail-fast injections are decided without the slow ones.
# Every class the suite declares must be here - checked before anything runs,
# because a class left out would simply never run - plus the one class of the
# SEC acquisition suite that covers what the model path imports from it: the
# gh reader's narrowed environment.
GH_READER = "tests.vnext.test_historical_source_acquisition.TheGithubReaderPassesGhOnlyWhatItNeeds"
ORDER = ("TheEgressGateNamesExactlyOneNewCaller", "TheFixturesNeverTouchAnAllowanceTheyDidNotWrite",
         GH_READER, "OnlyIssue47sOwnAuthorityReachesTheCallPath",
         "TheApprovalIsReadStrictly", "TheLedgerCannotBeResetByDeletingIt",
         "TheLimitIsCumulativeAndTheAllowanceIsTheAuthoritys", "OnlyTheRequestsTheApprovalNamesAreClaimed",
         "EveryCallIsCountedOnceAndStopsWhereTheCountCannotBeTrusted",
         "TheLivePathSendsThePlannedBytesOnceThroughTheControlledOpener",
         "ACompleteAssessmentRegistersOnlyFromItsOwnSlots",
         "AnE01ConfirmationIsOneCountedCallOnTheSamePath",
         "AD02ReviewIsOneCountedCallOnTheSamePath")
BOUNDARY = ("scripts/vnext/invocation_control.py", "scripts/vnext/ai_adapter.py",
            "tools/check_provider_egress.py")
BOUND = ("scripts/vnext/historical_model_calls.py", "scripts/vnext/historical_model_egress.py",
         "scripts/vnext/historical_source_acquisition.py", "tools/vnext_historical_model.py",
         *BOUNDARY, "tools/vnext_mint_historical_requirement.py",
         "tests/vnext/test_historical_model_egress.py",
         # The generation's snapshot: the live path requires the receipt to
         # bind it (historical_model_calls.CALL_PATH_FILES).
         "requirements/issue_47_v1/baseline_manifest.json",
         "tests/vnext/test_historical_source_acquisition.py", HERE + "/verify.py", PATCH)
CALLS = "scripts/vnext/historical_model_calls.py"
EGRESS = "scripts/vnext/historical_model_egress.py"
SEC = "scripts/vnext/historical_source_acquisition.py"
TESTS = "tests/vnext/test_historical_model_egress.py"
INJECTIONS = [
    ("A_REQUEST_MAY_BE_REDRAWN", CALLS,
     [('        _need(request_digest not in state["requests"],\n'
       '              "ISSUE_47_MODEL_REQUEST_ALREADY_CLAIMED_NO_REDRAW")\n', "")]),
    ("A_SLOT_WITHOUT_A_TERMINAL_DOES_NOT_STOP", CALLS,
     [('                stopped.append(slot.name + "=UNKNOWN_PENDING_RECONCILIATION")\n', "")]),
    ("HTTP_402_DOES_NOT_STOP", CALLS,
     [('STOPS = frozenset({"HTTP_402", ', 'STOPS = frozenset({')]),
    ("UNKNOWN_USAGE_DOES_NOT_STOP", CALLS,
     [('"USAGE_UNKNOWN", "CONTEXT_REFERENCE_MISMATCH", "CONTEXT_LIMIT"})',
       '"CONTEXT_REFERENCE_MISMATCH", "CONTEXT_LIMIT"})'),
      ('        stop = stop or "USAGE_UNKNOWN"\n', "        pass\n")]),
    # From here, one per finding of the independent security review
    # (independent-review-2026-09-27/README.md), each broken on its own.
    # M1: a count or a stop released by deleting files.
    ("SLOTS_ARE_COUNTED_WITHOUT_THE_CLAIM_LOG", CALLS,
     [('        _need(len(slots) == len(claims), "ISSUE_47_MODEL_LEDGER_CLAIM_SET_CHANGED:"',
       '        _need(True or len(slots) == len(claims), "ISSUE_47_MODEL_LEDGER_CLAIM_SET_CHANGED:"')]),
    ("THE_ANCHOR_IS_INSIDE_THE_ROOT", CALLS,
     [('        return root.parent / ("." + root.name + ".initialized.json")',
       '        return root / ".initialized.json"')]),
    ("THE_STOP_IS_READ_FROM_THE_TERMINAL", CALLS,
     [('            execution, _wire, stop = _slot_evidence(path=slot, intent=intent, live=self.live)\n',
       '            execution, _wire, stop = _slot_evidence(path=slot, intent=intent, live=self.live)\n'
       '            stop = terminal["stop_reason"]\n')]),
    # L1: ledger roots compared as strings.
    ("A_LEDGER_ROOT_MAY_BE_AN_ALIAS", CALLS,
     [('              and not any(path.is_symlink() for path in [self.root, *self.root.parents]),',
       '              and not any(False for path in [self.root, *self.root.parents]),')]),
    ("THE_SEC_ROOT_IS_COMPARED_AS_TEXT", CALLS,
     [('        for mine, theirs in ((real(budget_root), real(other)),\n'
       '                             (PurePosixPath(budget_root.casefold()), PurePosixPath(other.casefold()))):',
       '        for mine, theirs in ((PurePosixPath(budget_root), PurePosixPath(other)),):')]),
    # M2: approvals read last-key-wins, and an edited approval.
    ("THE_POLICY_IS_READ_LAST_KEY_WINS", CALLS,
     [('        policy = strict_json_loads(text=path.read_text(encoding="utf-8"))',
       '        policy = json.loads(path.read_text(encoding="utf-8"))')]),
    ("THE_APPROVAL_IS_READ_LAST_KEY_WINS", CALLS,
     [('        approved = strict_json_loads(text=comment["body"])',
       '        approved = json.loads(comment["body"])')]),
    ("AN_EDITED_APPROVAL_IS_ACCEPTED", SEC,
     [('          and comment.get("created_at") == comment.get("updated_at"),',
       '          and True,')]),
    # M3, the part code can hold: the approval names the verified receipt.
    ("THE_APPROVED_RECEIPT_IS_NOT_CHECKED", CALLS,
     [('    _need(receipt["receipt_id"] == receipt_id, "ISSUE_47_MODEL_WIRING_RECEIPT_IS_NOT_THE_APPROVED_ONE")',
       '    _need(True or receipt["receipt_id"] == receipt_id, "ISSUE_47_MODEL_WIRING_RECEIPT_IS_NOT_THE_APPROVED_ONE")')]),
    # M3, the rest code can hold: the approval names the exact requests, and
    # the verified receipt binds the generation's snapshot.
    ("THE_SCOPE_IGNORES_THE_REQUEST_DIGEST", CALLS,
     [('        covering = [name for name in covering if request_digest in named[name]]',
       '        covering = list(covering)')]),
    ("THE_LEDGER_TRUSTS_THE_CALLER_S_GRANTS", CALLS,
     [('        _need(bool(grants) and all(name in allowed and request_digest in allowed[name]',
       '        _need(True or bool(grants) and all(name in allowed and request_digest in allowed[name]')]),
    ("THE_RECEIPT_NEED_NOT_BIND_THE_SNAPSHOT", CALLS,
     [('                   "requirements/issue_47_v1/baseline_manifest.json")',
       '                   )')]),
    # L2: a send outside a counted slot.
    ("A_SEND_NEED_NOT_BE_COUNTED", EGRESS,
     [('        _need(self.ledger.claimed_slot(path=self.path, intent=self.intent),\n'
       '              "ISSUE_47_MODEL_SEND_WITHOUT_A_COUNTED_SLOT")\n', "")]),
    # L3: a source that is only re-hashed, not rebuilt from the filing.
    ("THE_SOURCE_IS_NOT_REBUILT_FROM_THE_FILING", CALLS,
     [('        _need(evidence_json_bytes(rebuilt) == self.source_bytes,',
       '        _need(True or evidence_json_bytes(rebuilt) == self.source_bytes,')]),
    # L4: a context overrun, a missing tokenizer, the order of the two checks.
    ("A_CONTEXT_OVERRUN_DOES_NOT_STOP", CALLS,
     [('"CONTEXT_REFERENCE_MISMATCH", "CONTEXT_LIMIT"})', '"CONTEXT_REFERENCE_MISMATCH"})')]),
    ("A_LIVE_CALL_MAY_BE_PLANNED_WITHOUT_THE_REFERENCE_TOKENIZER", EGRESS,
     [('    _need(not ledger.live or plan["observability"]["estimator_method"] == "PINNED_REFERENCE_CHAT_FORMAT",',
       '    _need(True or not ledger.live or plan["observability"]["estimator_method"] == "PINNED_REFERENCE_CHAT_FORMAT",')]),
    ("THE_LIMIT_IS_ANSWERED_BEFORE_THE_REFERENCE", EGRESS,
     [('            if usage["input_tokens"] is not None and usage["input_tokens"] != reference_input:\n'
       '                error_class = "CONTEXT_REFERENCE_MISMATCH"\n',
       '            error_class = usage_error(raw, expected_prompt_tokens=reference_input,\n'
       '                                      enforce_total_context=True)\n')]),
    # L6: the suite's fixtures and a tree's own allowance.
    ("THE_FIXTURES_OVERWRITE_A_REAL_ALLOWANCE", TESTS,
     [('            raise unittest.SkipTest("REFUSED: an allowance or fixture directory already exists in this tree")',
       '            pass')]),
    ("THE_FIXTURES_REMOVE_WHAT_THEY_DID_NOT_WRITE", TESTS,
     [('        raise AssertionError("FIXTURE_REPLACED_BY_SOMETHING_ELSE:" + relative)',
       '        pass')]),
    # L7: gh run with the caller's whole environment.
    ("GH_GETS_THE_WHOLE_ENVIRONMENT", SEC,
     [('    return {name: os.environ[name] for name in GH_ENVIRONMENT if name in os.environ}',
       '    return dict(os.environ)')]),
    # The runner the owner runs adds a loop and two rules; each is broken on its own.
    ("THE_RUNNER_GOES_ON_PAST_A_STOP", "tools/vnext_historical_model.py",
     [('                if outcome["stop_reason"]:\n'
       '                    stop = (metric_id + ":" + company_id + ":" + report_end + ":"\n'
       '                            + outcome["stop_reason"])\n'
       '                    break\n', '')]),
    # E01 on the same path: each metric held to its own request type, its own
    # response contract, and its registration in the ledger's own mode.
    ("A_REQUEST_NEED_NOT_BE_ITS_METRIC_S_TYPE", EGRESS,
     [('    _need(request_fields.get("record_type") == REQUEST_TYPES.get(prepared.metric_id),',
       '    _need(True or request_fields.get("record_type") == REQUEST_TYPES.get(prepared.metric_id),')]),
    ("AN_E01_ANSWER_IS_HELD_TO_D04_S_CONTRACT", EGRESS,
     [('    if prepared.metric_id == "D04":\n        from .d04_native_assessment import',
       '    if True:\n        from .d04_native_assessment import')]),
    ("AN_E01_REGISTRATION_TAKES_A_MODE_OF_ITS_OWN", EGRESS,
     [('                                     output=output, mode=ledger.mode)',
       '                                     output=output, mode="LIVE")')]),
    ("THE_RUNNER_REGISTERS_AN_INCOMPLETE_POSITION", "tools/vnext_historical_model.py",
     [('        if not row["unsuccessful"]:\n', '        if True:\n')]),
    # D02 on the same path: its own response contract, and its registration in
    # the ledger's own mode.
    ("A_D02_ANSWER_IS_HELD_TO_E01_S_CONTRACT", EGRESS,
     [('    if prepared.metric_id == "D02":\n        from .historical_legal_review import',
       '    if False:\n        from .historical_legal_review import')]),
    ("A_D02_REGISTRATION_TAKES_A_MODE_OF_ITS_OWN", EGRESS,
     [('                               output=output, mode=ledger.mode)',
       '                               output=output, mode="LIVE")')]),
    # The three checks the review neutralized at once without any case failing.
    ("THE_SEND_DOES_NOT_RECHECK_ITS_RESERVATION", EGRESS,
     [('        _need(reservation["owner_process_id"] == os.getpid()',
       '        _need(True or reservation["owner_process_id"] == os.getpid()')]),
    ("A_LIVE_LEDGER_MAY_BE_ANYWHERE", EGRESS,
     [('        _need(ledger.root == Path(prepared.allowance["budget_root"]),',
       '        _need(True or ledger.root == Path(prepared.allowance["budget_root"]),')]),
    ("A_LEDGER_FOR_ANOTHER_ALLOWANCE_IS_USED", EGRESS,
     [('    _need(ledger.binding["delegation_url"] == prepared.allowance["delegation_url"]',
       '    _need(True or ledger.binding["delegation_url"] == prepared.allowance["delegation_url"]')]),
    ("NO_CUMULATIVE_LIMIT", CALLS,
     [('        _need(state["counts"][0] + 1 <= self.binding["limits"][0]\n',
       '        _need(True or state["counts"][0] + 1 <= self.binding["limits"][0]\n')]),
    ("A_CALLERS_ALLOWANCE_IS_TRUSTED", CALLS,
     [('    _need(all(policy[key] == value for key, value in _allowance_hashes(allowance).items()),',
       '    _need(True or all(policy[key] == value for key, value in _allowance_hashes(allowance).items()),')]),
    ("THE_ADAPTER_MATCHES_THE_CLASS_NAME_ONLY", "scripts/vnext/ai_adapter.py",
     [('    if (type(prepared_request).__module__ == __package__ + ".historical_model_calls"\n'
       '            and type(prepared_request).__name__ == "HistoricalSemanticRequest"):',
       '    if (type(prepared_request).__name__ == "HistoricalSemanticRequest"):')]),
    ("NO_SOURCE_CHECK_AT_THE_SOCKET", EGRESS,
     [("                source_check()\n", ""),
      ("                    before_socket_open=source_check)", "                    )")]),
    ("NO_GITHUB_RECHECK_BEFORE_THE_SOCKET", EGRESS,
     [("                model_allowance(repo_root=ROOT, delegation_reader=github_comment_reader)\n",
       "")]),
    ("RECORDED_BYTES_ARE_ONLY_REFUSED_AFTER_THE_CLAIM", EGRESS,
     [('        _need(recorded_wire is None, "ISSUE_47_MODEL_RECORDED_BYTES_CANNOT_RUN_LIVE")\n'
       '        _need(ledger.root', '        _need(ledger.root')]),
    ("A_SECOND_TRANSPORT_CALLER", EGRESS,
     [('    from sec_http import write_immutable_bytes\n',
       '    from sec_http import write_immutable_bytes\n'
       '    from . import ai_adapter as _adapter\n'
       '    if False:\n'
       '        _adapter._build_repository_transport(policy=None)\n')]),
    ("REGISTRATION_TAKES_A_MODE_OF_ITS_OWN", EGRESS,
     [("                               outputs=outputs, mode=ledger.mode)",
       '                               outputs=outputs, mode="LIVE")')]),
    ("A_FAILED_SLOT_MAY_BE_REGISTERED", EGRESS,
     [('_need(terminal["intent_id"] == intent["intent_id"] and terminal["status"] == "SUCCEEDED"\n'
       '              and terminal["stop_reason"] == "", "ISSUE_47_MODEL_SLOT_DID_NOT_SUCCEED")',
       '_need(terminal["intent_id"] == intent["intent_id"], "ISSUE_47_MODEL_SLOT_DID_NOT_SUCCEED")')]),
    ("THE_CONTROLLER_BRANCH_IS_ABSENT", "scripts/vnext/invocation_control.py",
     [('    if requirement.get("requirement_id") == "issue_47_v1":',
       '    if requirement.get("requirement_id") == "issue_47_v1_NOT":')]),
    ("PLANS_MAY_NOT_KEEP_AN_UNAVAILABLE_PRICE", "scripts/vnext/invocation_control.py",
     [('.get("requirement_id") in {"issue_28_v14", "issue_47_v1"})',
       '.get("requirement_id") in {"issue_28_v14"})')]),
    # The caller is listed in both exact sets; each is broken on its own, so a
    # gate that checked only one of them is seen.
    ("THE_GATE_DOES_NOT_LIST_THE_TRANSPORT_CALLER", "tools/check_provider_egress.py",
     [('    ("scripts/vnext/historical_model_egress.py", "_Transport.send"),\n}\n'
       'ALLOWED_EGRESS_CAPABILITY_REFERENCES = {\n',
       '}\nALLOWED_EGRESS_CAPABILITY_REFERENCES = {\n')]),
    ("THE_GATE_DOES_NOT_LIST_THE_CAPABILITY_REFERENCE", "tools/check_provider_egress.py",
     [('ALLOWED_EGRESS_CAPABILITY_REFERENCES = {\n'
       '    ("scripts/vnext/continuous_semantic_calls.py", "_Transport.send"),\n'
       '    ("scripts/vnext/historical_model_egress.py", "_Transport.send"),\n',
       'ALLOWED_EGRESS_CAPABILITY_REFERENCES = {\n'
       '    ("scripts/vnext/continuous_semantic_calls.py", "_Transport.send"),\n')]),
]


# The class each injection is written against: the one holding the case that
# names the property it breaks. Every injection has one and every one is a
# class the suite declares, which main() checks before anything runs.
LIVE = "TheLivePathSendsThePlannedBytesOnceThroughTheControlledOpener"
COUNTED = "EveryCallIsCountedOnceAndStopsWhereTheCountCannotBeTrusted"
AUTHORITY = "OnlyIssue47sOwnAuthorityReachesTheCallPath"
LEDGER = "TheLedgerCannotBeResetByDeletingIt"
APPROVAL = "TheApprovalIsReadStrictly"
LIMIT = "TheLimitIsCumulativeAndTheAllowanceIsTheAuthoritys"
NAMED = "OnlyTheRequestsTheApprovalNamesAreClaimed"
E01 = "AnE01ConfirmationIsOneCountedCallOnTheSamePath"
D02 = "AD02ReviewIsOneCountedCallOnTheSamePath"
COMPLETE = "ACompleteAssessmentRegistersOnlyFromItsOwnSlots"
FIXTURES_CLASS = "TheFixturesNeverTouchAnAllowanceTheyDidNotWrite"
GATE = "TheEgressGateNamesExactlyOneNewCaller"
EXPECTED = {
    "A_REQUEST_MAY_BE_REDRAWN": COUNTED, "A_SLOT_WITHOUT_A_TERMINAL_DOES_NOT_STOP": COUNTED,
    "HTTP_402_DOES_NOT_STOP": LIVE, "UNKNOWN_USAGE_DOES_NOT_STOP": COUNTED,
    "SLOTS_ARE_COUNTED_WITHOUT_THE_CLAIM_LOG": LEDGER, "THE_ANCHOR_IS_INSIDE_THE_ROOT": LEDGER,
    "THE_STOP_IS_READ_FROM_THE_TERMINAL": LEDGER, "A_LEDGER_ROOT_MAY_BE_AN_ALIAS": LEDGER,
    "THE_SEC_ROOT_IS_COMPARED_AS_TEXT": APPROVAL, "THE_POLICY_IS_READ_LAST_KEY_WINS": APPROVAL,
    "THE_APPROVAL_IS_READ_LAST_KEY_WINS": APPROVAL, "AN_EDITED_APPROVAL_IS_ACCEPTED": APPROVAL,
    "THE_APPROVED_RECEIPT_IS_NOT_CHECKED": APPROVAL,
    "THE_SCOPE_IGNORES_THE_REQUEST_DIGEST": NAMED, "THE_LEDGER_TRUSTS_THE_CALLER_S_GRANTS": NAMED,
    "THE_RECEIPT_NEED_NOT_BIND_THE_SNAPSHOT": NAMED,
    "A_SEND_NEED_NOT_BE_COUNTED": AUTHORITY, "THE_SOURCE_IS_NOT_REBUILT_FROM_THE_FILING": AUTHORITY,
    "A_CONTEXT_OVERRUN_DOES_NOT_STOP": LIVE,
    "A_LIVE_CALL_MAY_BE_PLANNED_WITHOUT_THE_REFERENCE_TOKENIZER": LIVE,
    "THE_LIMIT_IS_ANSWERED_BEFORE_THE_REFERENCE": LIVE,
    "THE_FIXTURES_OVERWRITE_A_REAL_ALLOWANCE": FIXTURES_CLASS,
    "THE_FIXTURES_REMOVE_WHAT_THEY_DID_NOT_WRITE": FIXTURES_CLASS,
    "GH_GETS_THE_WHOLE_ENVIRONMENT": GH_READER,
    "THE_RUNNER_GOES_ON_PAST_A_STOP": LIVE, "A_REQUEST_NEED_NOT_BE_ITS_METRIC_S_TYPE": E01,
    "AN_E01_ANSWER_IS_HELD_TO_D04_S_CONTRACT": E01, "AN_E01_REGISTRATION_TAKES_A_MODE_OF_ITS_OWN": E01,
    "THE_RUNNER_REGISTERS_AN_INCOMPLETE_POSITION": LIVE,
    "A_D02_ANSWER_IS_HELD_TO_E01_S_CONTRACT": D02, "A_D02_REGISTRATION_TAKES_A_MODE_OF_ITS_OWN": D02,
    "THE_SEND_DOES_NOT_RECHECK_ITS_RESERVATION": LIVE, "A_LIVE_LEDGER_MAY_BE_ANYWHERE": LIVE,
    "A_LEDGER_FOR_ANOTHER_ALLOWANCE_IS_USED": LEDGER, "NO_CUMULATIVE_LIMIT": LIMIT,
    "A_CALLERS_ALLOWANCE_IS_TRUSTED": LIMIT, "THE_ADAPTER_MATCHES_THE_CLASS_NAME_ONLY": AUTHORITY,
    "NO_SOURCE_CHECK_AT_THE_SOCKET": LIVE, "NO_GITHUB_RECHECK_BEFORE_THE_SOCKET": LIVE,
    "RECORDED_BYTES_ARE_ONLY_REFUSED_AFTER_THE_CLAIM": LIVE, "A_SECOND_TRANSPORT_CALLER": GATE,
    "REGISTRATION_TAKES_A_MODE_OF_ITS_OWN": COMPLETE, "A_FAILED_SLOT_MAY_BE_REGISTERED": COMPLETE,
    "THE_CONTROLLER_BRANCH_IS_ABSENT": AUTHORITY, "PLANS_MAY_NOT_KEEP_AN_UNAVAILABLE_PRICE": LIMIT,
    "THE_GATE_DOES_NOT_LIST_THE_TRANSPORT_CALLER": GATE,
    "THE_GATE_DOES_NOT_LIST_THE_CAPABILITY_REFERENCE": GATE,
}


def _run(arguments, **kwargs):
    return subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, **kwargs)


FIXTURES = ("setUpClass", "setUpModule", "tearDownClass", "tearDownModule")


def _failures(lines):
    """Each FAIL/ERROR block: the case, its class for a fixture, and the last line it raised."""
    rows = []
    for index, line in enumerate(lines):
        if not line.startswith(("FAIL: ", "ERROR: ")):
            continue
        case, _, where = line.split(": ", 1)[1].partition(" (")
        raised = ""
        for later in lines[index + 2:]:
            if later.startswith(("=" * 20, "-" * 20)):
                break
            if later.strip():
                raised = later.strip()
        rows.append({"case": case, **({"class": where.rstrip(")").split(".")[-1]}
                                      if case in FIXTURES else {}), "raised": raised[:300]})
    return rows


def _outcome(code, failures):
    """Only a failing case is a catch; a fixture failure is one, recorded as such."""
    if code == 0:
        return "NOT_CAUGHT"
    if any(row["case"] not in FIXTURES for row in failures):
        return "CAUGHT"
    return "CAUGHT_AT_FIXTURE" if failures else "FAILED_OUTSIDE_ANY_CASE"


def _declared_classes():
    """The TestCase classes the suite file declares, read from its source rather than imported."""
    import ast
    tree = ast.parse((ROOT / TESTS).read_text(encoding="utf-8"))
    return sorted(node.name for node in tree.body if isinstance(node, ast.ClassDef)
                  and not node.name.startswith("_")
                  and any(getattr(base, "id", getattr(base, "attr", "")) in ("_Isolated", "TestCase")
                          for base in node.bases))


def _suite(fail_fast, classes=ORDER):
    names = [name if name.startswith("tests.") else SUITE + "." + name for name in classes]
    # Generous on purpose: the whole suite ran 880 s alone and far longer beside
    # a batch, and a timeout here would stop the harness without a receipt.
    run = _run([sys.executable, "-m", "unittest", *(["-f"] if fail_fast else []), *names],
               timeout=14400)
    lines = run.stderr.strip().splitlines()
    failures = _failures(lines)
    return run.returncode, failures, (lines[-1] if lines else ""), next(
        (line for line in lines if line.startswith("Ran ")), "")


def _mint(check=False):
    return _run([sys.executable, "tools/vnext_mint_historical_requirement.py",
                 *(["--check"] if check else [])])


def _snapshot():
    return {path.relative_to(ROOT).as_posix(): path.read_bytes()
            for path in sorted((ROOT / "requirements/issue_47_v1").glob("*")) if path.is_file()}


def _recorded_by_the_snapshot():
    manifest = json.loads((ROOT / "requirements/issue_47_v1/baseline_manifest.json").read_text(
        encoding="utf-8"))
    return set(manifest["execution_authority"]["files"])


def _sha(path):
    import hashlib
    raw = (ROOT / path).read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def _generation_manifests():
    """Each generation's manifest bytes, so a reader can tell which snapshots were measured.

    A tree that is behind the repository measures stale generations; the first
    sealing attempt ran in one and was stopped when a comparison showed it.
    """
    return {manifest.parent.name: _sha(manifest.relative_to(ROOT).as_posix())
            for manifest in sorted((ROOT / "requirements").glob("*/baseline_manifest.json"))}


def _moved_generations():
    moved = {}
    for manifest in sorted((ROOT / "requirements").glob("*/baseline_manifest.json")):
        files = json.loads(manifest.read_text(encoding="utf-8")).get(
            "execution_authority", {}).get("files", {})
        bound = {relative: files[relative] for relative in BOUNDARY if relative in files}
        differs = sorted(relative for relative, binding in bound.items()
                         if binding != _sha(relative))
        if bound:
            moved[manifest.parent.name] = differs
    return moved


def main():
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "tools"))
    applied = _run(["git", "apply", "-R", "--check", PATCH])
    minted = _mint(check=True)
    if applied.returncode or minted.returncode:
        print(applied.stderr, minted.stdout, minted.stderr)
        return 2
    local = sorted(name for name in ORDER if not name.startswith("tests."))
    if local != _declared_classes():
        print("ORDER_DOES_NOT_COVER_THE_SUITE", local, _declared_classes())
        return 2
    names = [name for name, _, _ in INJECTIONS]
    if sorted(names) != sorted(EXPECTED) or not set(EXPECTED.values()) <= set(ORDER):
        print("EVERY_INJECTION_NEEDS_ONE_EXPECTED_CLASS_THE_SUITE_DECLARES",
              sorted(set(names) ^ set(EXPECTED)), sorted(set(EXPECTED.values()) - set(ORDER)))
        return 2
    before = {path: _sha(path) for path in BOUND}
    snapshot = _snapshot()
    recorded = _recorded_by_the_snapshot()
    from check_provider_egress import check_provider_egress
    gate = check_provider_egress(repo_root=ROOT)
    code, failures, summary, ran = _suite(fail_fast=False)
    suite = {"returncode": code, "failed": [row["case"] for row in failures],
             "summary": summary, "ran": ran}
    print("suite", suite, flush=True)
    injections = []
    for name, path, edits in INJECTIONS:
        target = ROOT / path
        original = target.read_bytes()
        text = original.decode("utf-8")
        for old, _ in edits:
            assert text.count(old) == 1, (name, old[:60], text.count(old))
        for old, new in edits:
            text = text.replace(old, new)
        row = {"id": name, "file": path, "minted_for_the_injection": path in recorded}
        try:
            compile(text, path, "exec")
        except SyntaxError as error:
            row.update(outcome="INJECTION_DOES_NOT_COMPILE", error=str(error))
            injections.append(row)
            print(json.dumps(row), flush=True)
            continue
        try:
            target.write_text(text, encoding="utf-8")
            if row["minted_for_the_injection"]:
                assert _mint().returncode == 0, name
            expected = EXPECTED[name]
            code_i, failures_i, summary_i, _ = _suite(fail_fast=True, classes=(expected,))
            row.update(expected_class=expected,
                       expected_class_outcome=_outcome(code_i, failures_i))
            if row["expected_class_outcome"] in ("NOT_CAUGHT", "FAILED_OUTSIDE_ANY_CASE"):
                # The class written for it did not catch it; the whole suite
                # still might, and a catch there is recorded as one elsewhere.
                code_i, failures_i, summary_i, _ = _suite(fail_fast=True)
                row["whole_suite_run"] = True
        finally:
            target.write_bytes(original)
            if row["minted_for_the_injection"]:
                _mint()
        if _snapshot() != snapshot:
            print(json.dumps({"id": name, "stopped": "SNAPSHOT_DID_NOT_COME_BACK"}))
            return 2
        row.update(outcome=_outcome(code_i, failures_i),
                   first_caught_by=[failure["case"] for failure in failures_i],
                   failures=failures_i, suite_result=summary_i)
        injections.append(row)
        print(json.dumps(row), flush=True)
    moved = _moved_generations()
    restored = (_run(["git", "apply", "-R", "--check", PATCH]).returncode == 0
                and _mint(check=True).returncode == 0 and _snapshot() == snapshot
                and {path: _sha(path) for path in BOUND} == before)
    checks = {"patch_is_applied_here": applied.returncode == 0,
              "every_declared_class_ran": local == _declared_classes(),
              "snapshot_minted_for_these_bytes": minted.returncode == 0,
              "egress_gate_passes": gate["status"] == "PASS",
              "suite_passes": code == 0,
              "every_injection_compiles": all(
                  r["outcome"] != "INJECTION_DOES_NOT_COMPILE" for r in injections),
              "every_injection_caught": all(
                  r["outcome"] in ("CAUGHT", "CAUGHT_AT_FIXTURE") for r in injections),
              "tree_restored_after_injections": restored}
    body = {"record_type": "ISSUE_47_MODEL_EGRESS_OFFLINE_VERIFICATION",
            "requirement_id": "issue_47_v1", "all_checks_passed": all(checks.values()),
            "checks": checks, "calls": {"provider": 0, "paid": 0, "sec": 0},
            "suite": suite, "egress_gate": {
                "repository_transport_factories": gate["repository_transport_factories"],
                "egress_capability_references": gate["egress_capability_references"],
                "gate_receipt_id": gate["gate_receipt_id"]},
            "fault_injections": injections,
            "generations_that_record_the_boundary_files": moved,
            "generation_manifests_measured": _generation_manifests(),
            "what_applying_the_patch_moves": (
                "every generation listed above records these files by bytes; those whose list "
                "is non-empty no longer validate their execution authority in a tree with the "
                "patch applied, so the patch cannot be applied beside them unchanged"),
            "bound_files": {path: _sha(path) for path in BOUND},
            "production_authorized": False, "live_call_authorized": False}
    from vnext.canonical import content_hash
    receipt = {**body, "receipt_id": content_hash(value=body)}
    if not receipt["all_checks_passed"]:
        print(json.dumps(checks, indent=1))
        return 2
    (ROOT / OUTPUT).write_text(json.dumps(receipt, ensure_ascii=False, indent=1, sort_keys=True)
                               + "\n", encoding="utf-8")
    print(json.dumps({"receipt_id": receipt["receipt_id"], "checks": checks}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
