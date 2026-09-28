"""Verify Issue #47's model-egress patch offline, in a tree where it is applied, and seal the result.

Run from the root of a runtime tree that carries the issue_47_v1 registration
patch, after applying this directory's egress-registration.patch and minting:

    git apply docs/evidence/issue47_history/model-egress/egress-registration.patch
    python3 tools/vnext_mint_historical_requirement.py
    python3 docs/evidence/issue47_history/model-egress/verify.py [--copies N]

It never runs in the repository checkout: the patch is not applied there, and
the controller refuses issue_47_v1 there (which the repository's own
tests/vnext/test_historical_model_calls.py asserts). Steps, each recorded:

1. the patch is the one applied here (``git apply -R --check``) and the
   snapshot is minted for these bytes;
2. the repository's egress gate passes and names the one new caller;
3. the verification suite passes (every case, network refused), and leaves
   this tree as it found it, file for file;
4. every fault injection is caught, and by which case - in worker copies of
   this tree, never in the tree itself. The owner approved running them in
   parallel as a contract change (Issue #47 comment 5870869079,
   docs/evidence/issue47_history/owner-decisions-2026-09-28/): N copies
   (``--copies``, default 3) are made after the suite has passed, and each
   must match one manifest of this tree - every file's path, size and
   SHA-256, ``.git`` included and ``__pycache__`` left out - when it is made
   and again when the last injection has run; this tree must still match it
   too. Each injection runs once, in its own process, in whichever copy is
   free, and is judged exactly as it was when they ran one after another. A
   copy that differs, a worker that fails or stops, or an injection that did
   not run exactly once blocks the seal. The receipt names the copies, the
   manifest's digest, where each injection ran and how long it took; the
   change is accepted when the same injections are caught by the same named
   cases as the sequential run. Each injection names
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
   snapshot still matches, and every bound file has the bytes it had before;
7. the creator journal (``.git/issue47-historical-assessments``) holds the
   files it held when the run began - after the suite, and after every
   injection in the copy that ran it, so a registration a case left behind
   stops the run by name instead of failing whatever case reads that source
   next.

Only if all of that holds is ``offline-verification.json`` sealed. Zero calls.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
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
         "TheLimitIsCumulativeAndTheAllowanceIsTheAuthoritys",
         "AMappingIsNotAnAllowanceAndALedgerIsNotAGrant", "OnlyTheRequestsTheApprovalNamesAreClaimed",
         "EveryCallIsCountedOnceAndStopsWhereTheCountCannotBeTrusted",
         "ASocketOpensOnlyForTheCountedSendItBelongsTo",
         "TheLivePathSendsThePlannedBytesOnceThroughTheControlledOpener",
         "ACompleteAssessmentRegistersOnlyFromItsOwnSlots",
         "AnE01ConfirmationIsOneCountedCallOnTheSamePath",
         "AD02ReviewIsOneCountedCallOnTheSamePath",
         # The repository's own unit classes for the ledger and the approval,
         # which hold the checks a re-review found no egress case broke alone.
         "tests.vnext.test_historical_model_calls.TheLedgerCountsEveryClaimAndStopsWhereItCannotTrustTheCount",
         "tests.vnext.test_historical_model_calls.TheAllowanceIsVerifiedNotMerelyPresent",
         "tests.vnext.test_historical_model_calls.TheApprovalIsRegisteredFromWhatWasPosted")
BOUNDARY = ("scripts/vnext/invocation_control.py", "scripts/vnext/ai_adapter.py",
            "tools/check_provider_egress.py")
BOUND = ("scripts/vnext/historical_model_calls.py", "scripts/vnext/historical_model_egress.py",
         "scripts/vnext/historical_source_acquisition.py", "tools/vnext_historical_model.py",
         *BOUNDARY, "tools/vnext_mint_historical_requirement.py",
         "tests/vnext/test_historical_model_egress.py",
         # The generation's snapshot: the live path requires the receipt to
         # bind it (historical_model_calls.CALL_PATH_FILES).
         "requirements/issue_47_v1/baseline_manifest.json",
         "tests/vnext/test_historical_source_acquisition.py", HERE + "/verify.py", PATCH,
         # What a LIVE registration must carry and the ledger it must come
         # from; and the D04 answer the suite registers, kept apart so the
         # suite loads no checkout code the call is not bound to.
         "scripts/vnext/historical_counted_calls.py", "tests/vnext/d04_synthetic_output.py",
         "tests/vnext/test_historical_model_calls.py")
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
     [('                   "USAGE_UNKNOWN", "CONTEXT_REFERENCE_MISMATCH", "CONTEXT_LIMIT",\n',
       '                   "CONTEXT_REFERENCE_MISMATCH", "CONTEXT_LIMIT",\n'),
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
     [('"USAGE_UNKNOWN", "CONTEXT_REFERENCE_MISMATCH", "CONTEXT_LIMIT",\n',
       '"USAGE_UNKNOWN", "CONTEXT_REFERENCE_MISMATCH",\n')]),
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
     [('                                     output=output, mode=ledger.mode, counted=counted)',
       '                                     output=output, mode="LIVE", counted=counted)')]),
    ("THE_RUNNER_REGISTERS_AN_INCOMPLETE_POSITION", "tools/vnext_historical_model.py",
     [('        if not row["unsuccessful"]:\n', '        if True:\n')]),
    # D02 on the same path: its own response contract, and its registration in
    # the ledger's own mode.
    ("A_D02_ANSWER_IS_HELD_TO_E01_S_CONTRACT", EGRESS,
     [('    if prepared.metric_id == "D02":\n        from .historical_legal_review import',
       '    if False:\n        from .historical_legal_review import')]),
    ("A_D02_REGISTRATION_TAKES_A_MODE_OF_ITS_OWN", EGRESS,
     [('        return register_review(request=request, company_id=first.company_id,\n'
       '                               period_selection_id=first.period_selection["selection_id"],\n'
       '                               output=output, mode=ledger.mode, counted=counted)',
       '        return register_review(request=request, company_id=first.company_id,\n'
       '                               period_selection_id=first.period_selection["selection_id"],\n'
       '                               output=output, mode="LIVE", counted=counted)')]),
    # The send's reservation check, part by part: a re-review removed every
    # part but the marker count at once and no case failed.
    ("THE_SEND_DOES_NOT_ASK_WHICH_PROCESS_RESERVED", EGRESS,
     [('    return (reservation["owner_process_id"] == os.getpid()\n'
       '            and reservation["owner_token_hash"]',
       '    return (True\n            and reservation["owner_token_hash"]')]),
    ("THE_SEND_DOES_NOT_ASK_WHICH_OWNER_RESERVED", EGRESS,
     [('            and reservation["owner_token_hash"] == content_hash(value=owner_token)\n', '')]),
    ("THE_SEND_DOES_NOT_ASK_WHICH_EXECUTION_RESERVED", EGRESS,
     [('            and reservation["execution_id"] == execution_id\n            and len(markers) == 1\n',
       '            and len(markers) == 1\n')]),
    ("THE_SEND_ACCEPTS_MORE_THAN_ONE_MARKER", EGRESS,
     [('            and len(markers) == 1\n            and markers[0]["ai_invocation_plan_id"]',
       '            and len(markers) >= 1\n            and markers[0]["ai_invocation_plan_id"]')]),
    ("THE_SEND_DOES_NOT_ASK_WHICH_PLAN_WAS_MARKED", EGRESS,
     [('            and markers[0]["ai_invocation_plan_id"] == plan["ai_invocation_plan_id"]\n', '')]),
    ("THE_SEND_DOES_NOT_ASK_WHICH_TRANSPORT_WAS_MARKED", EGRESS,
     [('            and markers[0]["transport_kind"] == transport_kind)',
       '            )')]),
    ("A_LIVE_LEDGER_MAY_BE_ANYWHERE", EGRESS,
     [('        _need(ledger.root == Path(prepared.allowance["budget_root"]),',
       '        _need(True or ledger.root == Path(prepared.allowance["budget_root"]),')]),
    ("A_LEDGER_FOR_ANOTHER_ALLOWANCE_IS_USED", EGRESS,
     [('    _need(ledger.binding["delegation_url"] == prepared.allowance["delegation_url"]',
       '    _need(True or ledger.binding["delegation_url"] == prepared.allowance["delegation_url"]')]),
    ("NO_CUMULATIVE_LIMIT", CALLS,
     [('        _need(state["counts"][0] + 1 <= self.binding["limits"][0]\n',
       '        _need(True or state["counts"][0] + 1 <= self.binding["limits"][0]\n')]),
    # A caller's mapping is held twice - to the authority's decision hashes and,
    # field for field, to the allowance file - so the property breaks only when
    # both checks go; each alone is the other's redundancy.
    ("A_CALLERS_ALLOWANCE_IS_TRUSTED", CALLS,
     [('    _need(all(policy[key] == value for key, value in _allowance_hashes(allowance).items()),',
       '    _need(True or all(policy[key] == value for key, value in _allowance_hashes(allowance).items()),'),
      ('          "ISSUE_47_MODEL_ALLOWANCE_IS_NOT_THE_ONE_THE_AUTHORITY_BOUND")\n'
       '    allowance_is_the_file_s(allowance)\n',
       '          "ISSUE_47_MODEL_ALLOWANCE_IS_NOT_THE_ONE_THE_AUTHORITY_BOUND")\n')]),
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
     [("                               outputs=outputs, mode=ledger.mode, counted=counted)",
       '                               outputs=outputs, mode="LIVE", counted=counted)')]),
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
    # From here, one per finding of the independent security re-review
    # (independent-review-2026-09-27-rereview/), each broken on its own.
    # A: a mapping that differs from the file only where no decision hash looks.
    ("A_MAPPING_IS_NOT_HELD_TO_THE_FILE", CALLS,
     [('    allowance_is_the_file_s(allowance)\n\n\ndef prepare_historical_requests',
       '\n\ndef prepare_historical_requests')]),
    ("A_LEDGER_A_MAPPING_DESCRIBED_MAY_CLAIM", CALLS,
     [('        _need(self.root == root\n'
       '              and self.binding == _ledger(allowance=allowance, root=root, live=True).binding,',
       '        _need(True or self.root == root\n'
       '              and self.binding == _ledger(allowance=allowance, root=root, live=True).binding,')]),
    # The digest an approval names covers every byte a call sends.
    ("THE_DIGEST_IS_ISSUE_28_S_SEMANTIC_ONE", CALLS,
     [('    from .continuous_semantic_calls import request_body\n'
       '    return "sha256:" + sha256_bytes(content=request_body(request, policy))\n',
       '    from .continuous_semantic_calls import request_digest\n'
       '    return "sha256:" + request_digest(request, policy)\n')]),
    # B: the adapter's hook released #47's bytes to any caller of the transport.
    ("THE_HOOK_RELEASES_BYTES_WITHOUT_A_COUNTED_SEND", CALLS,
     [('    held = _SENDING.get(threading.get_ident())\n'
       '    _need(held is not None and held[0] is request, "ISSUE_47_MODEL_TRANSPORT_WITHOUT_A_COUNTED_SEND")\n',
       '    held = _SENDING.get(threading.get_ident())\n'
       '    if held is None or held[0] is not request:\n'
       '        request.validate(policy)\n'
       '        return request.request_bytes, request.provider_request_body_bytes, request.output_schema_bytes\n')]),
    # C: emptying the root, or truncating its last claim, reset the ledger.
    ("THE_CLAIM_LOG_HAS_NO_COPY_BESIDE_THE_ROOT", CALLS,
     [('        _need(copy == claims, "ISSUE_47_MODEL_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR:"',
       '        _need(True or copy == claims, "ISSUE_47_MODEL_LEDGER_CLAIM_LOG_DIFFERS_FROM_ITS_MIRROR:"')]),
    # D: a LIVE registration without the counted calls that answered it.
    ("A_LIVE_CONFIRMATION_NEEDS_NO_CALLS", "scripts/vnext/historical_ma_confirmation.py",
     [('    _need(mode != "LIVE" or counted is not None, "E01_LIVE_CONFIRMATION_WITHOUT_COUNTED_CALLS")\n',
       '')]),
    ("A_LIVE_REVIEW_NEEDS_NO_CALLS", "scripts/vnext/historical_legal_review.py",
     [('    _need(mode != "LIVE" or counted is not None, "D02_LIVE_REVIEW_WITHOUT_COUNTED_CALLS")\n',
       '')]),
    ("A_LIVE_ASSESSMENT_NEEDS_NO_CALLS", "scripts/vnext/historical_semantic_results.py",
     [('    _need(mode != "LIVE" or counted is not None, "HISTORICAL_LIVE_ASSESSMENT_WITHOUT_COUNTED_CALLS")\n',
       '')]),
    ("A_COUNTED_CALL_NEED_NOT_BE_LIVE", "scripts/vnext/historical_counted_calls.py",
     [('          and binding.get("execution_mode") == mode, "ISSUE_47_COUNTED_CALLS_LEDGER_CHANGED")',
       '          , "ISSUE_47_COUNTED_CALLS_LEDGER_CHANGED")')]),
    ("A_COUNTED_CALL_NEED_NOT_HAVE_ANSWERED_WITH_THIS_OUTPUT", "scripts/vnext/historical_counted_calls.py",
     [('              and evidence.get("wire/assistant-output.bin") == sha256_bytes(content=output),\n',
       '              and True,\n'),
      ('              and wire["assistant_output_sha256"] == sha256_bytes(content=output),\n',
       '              and True,\n')]),
    # E: a test's LIVE leftovers read by a batch.
    ("A_LIVE_REGISTRATION_NEEDS_NO_REGISTERED_APPROVAL", "scripts/vnext/historical_counted_calls.py",
     [('    check_counted_calls(counted=counted, answered=answered, mode="LIVE")\n'
       '    return check_granted(counted=counted, repo_root=repo_root)\n',
       '    return check_counted_calls(counted=counted, answered=answered, mode="LIVE")\n')]),
    # H: a response nested past the parser's depth left the slot open.
    ("A_NESTED_ANSWER_ESCAPES_THE_CALL_PATH", EGRESS,
     [('        except (ValueError, KeyError, TypeError, RecursionError) as error:\n'
       '            raise control.SchemaViolationError(str(error)[:400]) from error\n',
       '        except (ValueError, KeyError, TypeError) as error:\n'
       '            raise control.SchemaViolationError(str(error)[:400]) from error\n')]),
    ("A_NESTED_RESPONSE_ESCAPES_THE_CALL_PATH", EGRESS,
     [('        except RecursionError as error:\n', '        except ZeroDivisionError as error:\n')]),
    # N7: a transport account that disagrees, after the charge.
    ("AN_OBSERVATION_MISMATCH_IS_RAISED_PAST_THE_RESPONSE", EGRESS,
     [('                if mismatch is not None:\n'
       '                    error_class = "TRANSPORT_OBSERVATION_CHANGED"\n'
       '                    error_detail = str(mismatch)[:400]\n',
       '                _need(mismatch is None, "ISSUE_47_MODEL_TRANSPORT_OBSERVATION_CHANGED")\n')]),
    ("AN_OBSERVATION_MISMATCH_DOES_NOT_STOP", CALLS,
     [('"CONTEXT_LIMIT",\n'
       '                   # The transport\'s own account of the call disagrees with the\n'
       '                   # bytes it was given: what was sent cannot be trusted.\n'
       '                   "TRANSPORT_OBSERVATION_CHANGED"})',
       '"CONTEXT_LIMIT"})')]),
    # L3 for E01 and D02: each of the two comparisons on its own.
    ("AN_E01_OR_D02_SOURCE_IS_NOT_REBUILT", CALLS,
     [('    _need(evidence_json_bytes(rebuilt) == self.source_bytes,\n'
       '          "ISSUE_47_MODEL_SOURCE_DOES_NOT_REBUILD_FROM_THE_FILING")\n'
       '    request = strict_json_loads(text=self.request_bytes.decode("utf-8"))\n'
       '    _need(request == rebuilt["request"]',
       '    request = strict_json_loads(text=self.request_bytes.decode("utf-8"))\n'
       '    _need(request == rebuilt["request"]')]),
    ("AN_E01_OR_D02_REQUEST_IS_NOT_COMPARED", CALLS,
     [('    _need(request == rebuilt["request"] and request["company_id"] == self.company_id',
       '    _need(request["company_id"] == self.company_id')]),
    # M1's sub-checks a re-review found no case broke alone.
    ("THE_CLAIMS_NEED_NOT_CHAIN", CALLS,
     [('                  and intent["previous_intent_id"] == previous,\n',
       '                  and True,\n')]),
    ("AN_EDITED_BINDING_IS_ACCEPTED", CALLS,
     [('        _need(strict_json_file(path=binding_path) == self.binding, "ISSUE_47_MODEL_LEDGER_BINDING_CHANGED")',
       '        _need(True or strict_json_file(path=binding_path) == self.binding, "ISSUE_47_MODEL_LEDGER_BINDING_CHANGED")')]),
    ("AN_EDITED_ANCHOR_IS_ACCEPTED", CALLS,
     [('        _need(strict_json_file(path=anchor) == self.binding,',
       '        _need(True or strict_json_file(path=anchor) == self.binding,')]),
    # M3, the parts code can hold about who posted the approval.
    ("THE_APPROVER_IS_A_LOGIN_ONLY", SEC,
     [('    _need(user.get("login") == policy["approver_login"] and user.get("id") == TRUSTED_APPROVER_ID\n'
       '          and user.get("type") == "User" and comment.get("author_association") == "OWNER",',
       '    _need(user.get("login") == policy["approver_login"],')]),
    ("A_MODEL_APPROVAL_MAY_BE_POSTED_THROUGH_AN_APP", CALLS,
     [('    _need("performed_via_github_app" in comment and comment["performed_via_github_app"] is None,',
       '    _need(True or "performed_via_github_app" in comment and comment["performed_via_github_app"] is None,')]),
    # K and P: unbound checkout code, and checkout bytecode, ran before a socket.
    ("UNBOUND_CHECKOUT_CODE_MAY_RUN", CALLS,
     [('    _need(not unbound, "ISSUE_47_MODEL_UNBOUND_CODE_LOADED:" + ",".join(sorted(unbound)[:8]))\n',
       '')]),
    ("CHECKOUT_BYTECODE_MAY_RUN", CALLS,
     [('    _need(not cached_in_the_checkout, "ISSUE_47_MODEL_CODE_READ_FROM_THE_CHECKOUT_S_BYTECODE:"\n'
       '          + ",".join(sorted(cached_in_the_checkout)[:8]))\n', '')]),
    ("NO_PRIVATE_BYTECODE_CACHE_IS_REQUIRED", CALLS,
     [('    _need(prefix is not None and Path(prefix).is_absolute() and Path(prefix).is_dir()',
       '    _need(True or prefix is not None and Path(prefix).is_absolute() and Path(prefix).is_dir()')]),
    # The runner makes its cache after importing the call path: what it
    # imported is compiled wherever the process's cache was, not into its own.
    # The suite loads the runner before any checkout code, as the owner does,
    # so this is seen - found when the suite first loaded it too late.
    ("THE_RUNNER_IMPORTS_THE_CHECKOUT_BEFORE_ITS_CACHE", "tools/vnext_historical_model.py",
     [('sys.pycache_prefix = tempfile.mkdtemp(prefix="issue47-model-bytecode-")\n', ''),
      ('from vnext import historical_model_egress as egress  # noqa: E402\n',
       'from vnext import historical_model_egress as egress  # noqa: E402\n'
       'sys.pycache_prefix = tempfile.mkdtemp(prefix="issue47-model-bytecode-")\n')]),
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
GRANTED = "AMappingIsNotAnAllowanceAndALedgerIsNotAGrant"
SOCKET = "ASocketOpensOnlyForTheCountedSendItBelongsTo"
LEDGER_UNIT = "tests.vnext.test_historical_model_calls.TheLedgerCountsEveryClaimAndStopsWhereItCannotTrustTheCount"
ALLOWANCE_UNIT = "tests.vnext.test_historical_model_calls.TheAllowanceIsVerifiedNotMerelyPresent"
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
    "A_LIVE_LEDGER_MAY_BE_ANYWHERE": LIVE,
    "THE_SEND_DOES_NOT_ASK_WHICH_PROCESS_RESERVED": SOCKET,
    "THE_SEND_DOES_NOT_ASK_WHICH_OWNER_RESERVED": SOCKET,
    "THE_SEND_DOES_NOT_ASK_WHICH_EXECUTION_RESERVED": SOCKET,
    "THE_SEND_ACCEPTS_MORE_THAN_ONE_MARKER": SOCKET,
    "THE_SEND_DOES_NOT_ASK_WHICH_PLAN_WAS_MARKED": SOCKET,
    "THE_SEND_DOES_NOT_ASK_WHICH_TRANSPORT_WAS_MARKED": SOCKET,
    "AN_OBSERVATION_MISMATCH_IS_RAISED_PAST_THE_RESPONSE": SOCKET,
    "AN_OBSERVATION_MISMATCH_DOES_NOT_STOP": SOCKET,
    "AN_E01_OR_D02_SOURCE_IS_NOT_REBUILT": E01, "AN_E01_OR_D02_REQUEST_IS_NOT_COMPARED": E01,
    "THE_CLAIMS_NEED_NOT_CHAIN": LEDGER_UNIT, "AN_EDITED_BINDING_IS_ACCEPTED": LEDGER_UNIT,
    "AN_EDITED_ANCHOR_IS_ACCEPTED": LEDGER_UNIT,
    "THE_APPROVER_IS_A_LOGIN_ONLY": ALLOWANCE_UNIT,
    "A_MODEL_APPROVAL_MAY_BE_POSTED_THROUGH_AN_APP": ALLOWANCE_UNIT,
    "A_LEDGER_FOR_ANOTHER_ALLOWANCE_IS_USED": LEDGER, "NO_CUMULATIVE_LIMIT": LIMIT,
    "A_CALLERS_ALLOWANCE_IS_TRUSTED": LIMIT, "THE_ADAPTER_MATCHES_THE_CLASS_NAME_ONLY": AUTHORITY,
    "NO_SOURCE_CHECK_AT_THE_SOCKET": LIVE, "NO_GITHUB_RECHECK_BEFORE_THE_SOCKET": LIVE,
    "RECORDED_BYTES_ARE_ONLY_REFUSED_AFTER_THE_CLAIM": LIVE, "A_SECOND_TRANSPORT_CALLER": GATE,
    "REGISTRATION_TAKES_A_MODE_OF_ITS_OWN": COMPLETE, "A_FAILED_SLOT_MAY_BE_REGISTERED": COMPLETE,
    "THE_CONTROLLER_BRANCH_IS_ABSENT": AUTHORITY, "PLANS_MAY_NOT_KEEP_AN_UNAVAILABLE_PRICE": LIMIT,
    "THE_GATE_DOES_NOT_LIST_THE_TRANSPORT_CALLER": GATE,
    "THE_GATE_DOES_NOT_LIST_THE_CAPABILITY_REFERENCE": GATE,
    "A_MAPPING_IS_NOT_HELD_TO_THE_FILE": GRANTED, "A_LEDGER_A_MAPPING_DESCRIBED_MAY_CLAIM": GRANTED,
    "THE_DIGEST_IS_ISSUE_28_S_SEMANTIC_ONE": GRANTED,
    "THE_HOOK_RELEASES_BYTES_WITHOUT_A_COUNTED_SEND": SOCKET,
    "THE_CLAIM_LOG_HAS_NO_COPY_BESIDE_THE_ROOT": LEDGER,
    "A_LIVE_CONFIRMATION_NEEDS_NO_CALLS": E01, "A_LIVE_REVIEW_NEEDS_NO_CALLS": D02,
    "A_LIVE_ASSESSMENT_NEEDS_NO_CALLS": COMPLETE, "A_COUNTED_CALL_NEED_NOT_BE_LIVE": E01,
    "A_COUNTED_CALL_NEED_NOT_HAVE_ANSWERED_WITH_THIS_OUTPUT": LIVE,
    "A_LIVE_REGISTRATION_NEEDS_NO_REGISTERED_APPROVAL": LIVE,
    "A_NESTED_ANSWER_ESCAPES_THE_CALL_PATH": E01, "A_NESTED_RESPONSE_ESCAPES_THE_CALL_PATH": E01,
    "UNBOUND_CHECKOUT_CODE_MAY_RUN": SOCKET, "CHECKOUT_BYTECODE_MAY_RUN": SOCKET,
    "NO_PRIVATE_BYTECODE_CACHE_IS_REQUIRED": SOCKET,
    "THE_RUNNER_IMPORTS_THE_CHECKOUT_BEFORE_ITS_CACHE": SOCKET,
}
# Dispatch order only: injections whose expected class ran longest in the
# 2026-09-28 pre-flight start first, so the last to start is a short one. It
# changes where and when an injection runs, never how it is judged.
SLOW_FIRST = (LIVE, SOCKET, COMPLETE, COUNTED, D02, LEDGER, NAMED)
COPIES_PREFIX = ".verify-copies-"


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
                  and any(getattr(base, "id", getattr(base, "attr", ""))
                          in ("_Isolated", "_LiveOpener", "TestCase")
                          for base in node.bases))


def _by_module(classes):
    """The classes' dotted names, one group per test module, each group in ``classes``' order."""
    groups = {}
    for name in classes:
        dotted = name if name.startswith("tests.") else SUITE + "." + name
        groups.setdefault(dotted.rsplit(".", 1)[0], []).append(dotted)
    return list(groups.values())


def _suite(fail_fast, classes=ORDER):
    """Run ``classes``, one process per test module, and report them as one run.

    One process per module because the call path checks the process it sends
    from: every checkout module that process loaded must be one the call's
    authority binds (historical_model_calls.loaded_code_holds). A test module
    loads what it imports, and the SEC acquisition suite imports the source
    discovery module and another suite's helpers, which no call path imports.
    The first run after that check existed put the gh reader's class in the
    egress suite's process, and every live case was refused for a module the
    owner's runner never loads - the check doing its job on a process no
    runner is. Each module in its own process is each suite as its own runner.
    """
    codes, failures, summaries, ran = [], [], [], 0
    for names in _by_module(classes):
        # Generous on purpose: the whole suite ran 880 s alone and far longer
        # beside a batch, and a timeout here would stop the harness without a
        # receipt. The suite compiles the checkout into a private cache, as
        # the owner's runner does: the call path refuses a socket in a process
        # that read the checkout's own __pycache__. The process also gets a
        # temporary directory of its own, removed with it: the runner makes
        # its bytecode cache there and never removes it, and so do the cases'
        # fixture roots when a process is ended early - 216 such directories
        # (1.5 GB) had piled up in the system's one before this was added.
        private = Path(tempfile.mkdtemp(prefix="issue47-verify-suite-"))
        (private / "bytecode").mkdir()
        (private / "tmp").mkdir()
        try:
            run = _run([sys.executable, "-m", "unittest", *(["-f"] if fail_fast else []), *names],
                       timeout=14400, env={**os.environ, "PYTHONPYCACHEPREFIX": str(private / "bytecode"),
                                           "TMPDIR": str(private / "tmp")})
        finally:
            shutil.rmtree(private, ignore_errors=True)
        lines = run.stderr.strip().splitlines()
        codes.append(run.returncode)
        failures.extend(_failures(lines))
        summaries.append(lines[-1] if lines else "")
        counted = next((line for line in lines if line.startswith("Ran ")), "")
        ran += int(counted.split()[1]) if counted else 0
        if fail_fast and run.returncode:
            break
    # "OK" only if every process said exactly that; "OK (skipped=N)" stays
    # itself, since a skipped class ran nothing.
    summary = "OK" if summaries and all(line == "OK" for line in summaries) else "; ".join(
        line for line in summaries if line != "OK")
    return (next((code for code in codes if code), 0), failures, summary,
            "Ran %d tests in %d processes, one per test module" % (ran, len(codes)))


def _mint(check=False):
    return _run([sys.executable, "tools/vnext_mint_historical_requirement.py",
                 *(["--check"] if check else [])])


JOURNAL = ".git/issue47-historical-assessments"


def _journal():
    """Every file in the creator journal, with its digest.

    It is in ``.git``, where no other check here looks. The first sealing run
    after the re-review stopped at its own suite: an injection in a pre-flight
    an hour earlier had dropped E01's "LIVE needs counted calls" check, a case
    registered LIVE and failed on that line before its cleanup, and the record
    stayed for the next case that read the window. The suite now puts the
    journal back after every case; this check is what would say it did not.
    """
    root = ROOT / JOURNAL
    if not root.is_dir():
        return {}
    return {path.relative_to(root).as_posix(): _sha(path.relative_to(ROOT).as_posix())["sha256"]
            for path in sorted(root.rglob("*")) if not path.is_dir()}


def _journal_moved(journal):
    """What the journal gained, lost or changed since ``journal``; empty when it came back."""
    now = _journal()
    return {"added": sorted(set(now) - set(journal)), "removed": sorted(set(journal) - set(now)),
            "changed": sorted(p for p in set(now) & set(journal) if now[p] != journal[p])}


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


def _file_sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(root):
    """Every entry under ``root`` but bytecode caches, sorted by path: size and SHA-256, or link target.

    What proves a worker copy is this tree. ``.git`` is in it - the creator
    journal lives there - and ``__pycache__`` is left out on both sides: the
    suite compiles into a private cache outside the tree, and the call path
    refuses to run code read from a checkout's own cache.
    """
    rows = []
    for directory, subdirectories, files in os.walk(root):
        here = Path(directory)
        for name in list(subdirectories):
            if name == "__pycache__" or (here / name).is_symlink():
                subdirectories.remove(name)
                if name != "__pycache__":
                    rows.append([(here / name).relative_to(root).as_posix(), "link",
                                 os.readlink(here / name)])
        for name in files:
            path = here / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                rows.append([relative, "link", os.readlink(path)])
            elif path.is_file():
                rows.append([relative, path.stat().st_size, _file_sha256(path)])
            else:
                rows.append([relative, "special", ""])
    return sorted(rows)


def _manifest_digest(rows):
    import hashlib
    return "sha256:" + hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
                                      .encode("utf-8")).hexdigest()


def _manifest_differences(expected, actual, limit=20):
    mine, theirs = ({row[0]: row[1:] for row in rows} for rows in (expected, actual))
    return {"missing": sorted(set(mine) - set(theirs))[:limit],
            "added": sorted(set(theirs) - set(mine))[:limit],
            "changed": sorted(path for path in set(mine) & set(theirs)
                              if mine[path] != theirs[path])[:limit]}


def _order():
    """Injection indices, slow expected classes first; ties keep the list's order."""
    rank = {name: position for position, name in enumerate(SLOW_FIRST)}
    return sorted(range(len(INJECTIONS)),
                  key=lambda index: (rank.get(EXPECTED[INJECTIONS[index][0]], len(SLOW_FIRST)), index))


def _inject(name, path, edits, *, snapshot, journal, recorded):
    """Break one check in this tree, run the class written to catch it, and put everything back.

    Returns the injection's row; a row with ``stopped`` means this tree did
    not come back - its snapshot or its creator journal - and nothing more
    may run in it.
    """
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
        return row
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
        row["stopped"] = "SNAPSHOT_DID_NOT_COME_BACK"
        return row
    moved_journal = _journal_moved(journal)
    if any(moved_journal.values()):
        row.update(stopped="CREATOR_JOURNAL_DID_NOT_COME_BACK", journal=moved_journal)
        return row
    row.update(outcome=_outcome(code_i, failures_i),
               first_caught_by=[failure["case"] for failure in failures_i],
               failures=failures_i, suite_result=summary_i)
    return row


def _worker(result, index, sealing_tree):
    """Run one injection in this copy and write its row - never in the sealing tree itself."""
    if ROOT == Path(sealing_tree).resolve() or COPIES_PREFIX not in ROOT.parent.name:
        print("A_WORKER_RUNS_ONLY_IN_A_COPY:" + str(ROOT))
        return 2
    name, path, edits = INJECTIONS[index]
    row = _inject(name, path, edits, snapshot=_snapshot(), journal=_journal(),
                  recorded=_recorded_by_the_snapshot())
    Path(result).write_text(json.dumps(row), encoding="utf-8")
    return 2 if row.get("stopped") else 0


def _make_copies(count):
    """``count`` real copies of this tree beside it. Real copies: the saved SEC evidence refuses
    a hard-linked file (``st_nlink != 1``), and a file an injection edits in place must not be
    shared with any other tree."""
    parent = Path(tempfile.mkdtemp(prefix=ROOT.name + COPIES_PREFIX, dir=ROOT.parent))
    roots = []
    for index in range(count):
        destination = parent / ("copy-%d" % index)
        shutil.copytree(ROOT, destination, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
        roots.append(destination)
    return parent, roots


def _stop_worker(process):
    """End a worker and everything it started; it leads its own process group."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=60)
    except ProcessLookupError:
        return
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def _elapsed(since):
    """Whole seconds since ``since``. The receipt's content hash refuses binary floats: the first
    parallel seal (2026-09-28) ran all 78 injections and then failed when it hashed a receipt whose
    timings were floats, so every timing the receipt carries comes from here."""
    return round(time.monotonic() - since)


def _dispatch(roots, order, results, receipt_check=None):
    """Run each injection once, in whichever copy is free, and stop everything at the first stop.

    ``receipt_check`` is called on every row as it arrives, so a row the receipt could not hold
    stops the run at the first injection instead of at sealing, hours later.

    Returns (rows by injection index, None), or (the rows so far, what stopped it).
    """
    pending, free, running, rows = list(order), list(range(len(roots))), {}, {}
    try:
        while pending or running:
            while free and pending:
                copy, index = free.pop(0), pending.pop(0)
                result = results / ("%03d.json" % index)
                with (results / ("%03d.err" % index)).open("w", encoding="utf-8") as errors:
                    process = subprocess.Popen(
                        [sys.executable, HERE + "/verify.py", "--worker", str(result), str(index),
                         str(ROOT)], cwd=roots[copy], stdout=subprocess.DEVNULL, stderr=errors,
                        start_new_session=True)
                running[copy] = (process, index, time.monotonic(), result)
            time.sleep(2)
            for copy, (process, index, started, result) in list(running.items()):
                if process.poll() is None:
                    continue
                del running[copy]
                row = json.loads(result.read_text(encoding="utf-8")) if result.is_file() else None
                if process.returncode != 0 or row is None or row.get("stopped"):
                    tail = (results / ("%03d.err" % index)).read_text(encoding="utf-8", errors="replace")
                    return rows, {"injection": INJECTIONS[index][0], "copy": copy,
                                  "returncode": process.returncode, "row": row,
                                  "stderr_tail": tail[-2000:]}
                row.update(copy=copy, seconds=_elapsed(started))
                rows[index] = row
                print(json.dumps(row), flush=True)
                if receipt_check is not None:
                    receipt_check(row)
                free.append(copy)
        return rows, None
    finally:
        for process, *_ in running.values():
            _stop_worker(process)


def _terminated(signum, frame):
    """A terminated run unwinds like an interrupted one, so its workers and copies are removed."""
    raise KeyboardInterrupt("terminated by signal " + str(signum))


def main():
    arguments = sys.argv[1:]
    if arguments[:1] == ["--worker"]:
        return _worker(arguments[1], int(arguments[2]), arguments[3])
    copies = 3
    if arguments[:1] == ["--copies"] and len(arguments) >= 2 and arguments[1].isdigit():
        copies, arguments = int(arguments[1]), arguments[2:]
    if arguments or copies < 1:
        print("usage: verify.py [--copies N], N >= 1")
        return 2
    started = time.monotonic()
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "tools"))
    from vnext.canonical import content_hash
    # The number type every timing in the receipt has, checked before the hours it would
    # otherwise take to find out that the receipt cannot be hashed.
    content_hash(value={"seconds": _elapsed(started)})
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
    # Every edit must hit exactly once, checked before anything runs. The
    # 2026-09-27 run found a target that was a substring of another line only
    # at its 31st injection, after the suite and 30 injections had run, and
    # stopped without a receipt; an
    # edit that does not apply says nothing about the code, so it is refused
    # here, where it costs nothing.
    misses = [(name, path, text.count(old)) for name, path, edits in INJECTIONS
              for text in [(ROOT / path).read_text(encoding="utf-8")]
              for old, _ in edits if text.count(old) != 1]
    if misses:
        print("AN_INJECTION_EDIT_DOES_NOT_HIT_EXACTLY_ONCE", misses)
        return 2
    # And every edited file must still compile: an injection that does not
    # compile breaks the import, not the check it names. The first sealing
    # attempt after the re-review's fixes found two such, where a removed line
    # left the line before it without its comma.
    broken = []
    for name, path, edits in INJECTIONS:
        text = (ROOT / path).read_text(encoding="utf-8")
        for old, new in edits:
            text = text.replace(old, new)
        try:
            compile(text, path, "exec")
        except SyntaxError as error:
            broken.append((name, path, str(error)))
    if broken:
        print("AN_INJECTION_DOES_NOT_COMPILE", broken)
        return 2
    before = {path: _sha(path) for path in BOUND}
    snapshot = _snapshot()
    journal = _journal()
    tree_before = _manifest(ROOT)
    from check_provider_egress import check_provider_egress
    gate = check_provider_egress(repo_root=ROOT)
    seconds = {}
    phase = time.monotonic()
    code, failures, summary, ran = _suite(fail_fast=False)
    seconds["suite"] = _elapsed(phase)
    suite = {"returncode": code, "failed": [row["case"] for row in failures],
             "summary": summary, "ran": ran}
    print("suite", suite, flush=True)
    moved_journal = _journal_moved(journal)
    if any(moved_journal.values()):
        print("THE_SUITE_DID_NOT_LEAVE_THE_CREATOR_JOURNAL_AS_IT_FOUND_IT",
              json.dumps(moved_journal), flush=True)
        return 2
    if not (code == 0 and summary == "OK"):
        # An injection "caught" by a suite that already fails says nothing
        # about the injection, and the injections take hours: stop here,
        # with no receipt, and let the failures be fixed first.
        print("THE_SUITE_DOES_NOT_PASS_SO_NO_INJECTION_IS_EVIDENCE",
              json.dumps(failures, indent=1), flush=True)
        return 2
    # The copies are made from this tree after the suite, so the suite must
    # have left it as it found it - every file, not only the journal and the
    # bound files - or the copies would carry what the suite left behind.
    tree = _manifest(ROOT)
    if tree != tree_before:
        print("THE_SUITE_DID_NOT_LEAVE_THE_TREE_AS_IT_FOUND_IT",
              json.dumps(_manifest_differences(tree_before, tree)), flush=True)
        return 2
    digest = _manifest_digest(tree)
    for number in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, _terminated)
    parent, roots, rows = None, [], {}
    results = Path(tempfile.mkdtemp(prefix="issue47-verify-results-"))
    try:
        phase = time.monotonic()
        parent, roots = _make_copies(copies)
        at_start = [_manifest(root) == tree for root in roots]
        seconds["copies"] = _elapsed(phase)
        if not all(at_start):
            print("A_COPY_DIFFERS_FROM_THE_SEALING_TREE", json.dumps(
                {str(index): _manifest_differences(tree, _manifest(root))
                 for index, root in enumerate(roots) if not at_start[index]}), flush=True)
            return 2
        phase = time.monotonic()
        rows, stop = _dispatch(roots, _order(), results,
                               receipt_check=lambda row: content_hash(value=row))
        seconds["injections"] = _elapsed(phase)
        if stop is not None:
            print("AN_INJECTION_STOPPED_THE_RUN", json.dumps(stop), flush=True)
            return 2
        phase = time.monotonic()
        at_end = [_manifest(root) == tree for root in roots]
        sealing_at_end = _manifest(ROOT) == tree
        seconds["final_manifests"] = _elapsed(phase)
        copy_names = [parent.name + "/" + root.name for root in roots]
    finally:
        if parent is not None:
            shutil.rmtree(parent, ignore_errors=True)
        shutil.rmtree(results, ignore_errors=True)
    injections = [rows[index] for index in sorted(rows)]
    moved = _moved_generations()
    restored = (_run(["git", "apply", "-R", "--check", PATCH]).returncode == 0
                and _mint(check=True).returncode == 0 and _snapshot() == snapshot
                and {path: _sha(path) for path in BOUND} == before)
    seconds["total"] = _elapsed(started)
    checks = {"patch_is_applied_here": applied.returncode == 0,
              "every_declared_class_ran": local == _declared_classes(),
              "snapshot_minted_for_these_bytes": minted.returncode == 0,
              "egress_gate_passes": gate["status"] == "PASS",
              # "OK (skipped=N)" is not a pass: a fixture that refuses to
              # start skips its class, and those cases would have run nothing.
              "suite_passes": code == 0 and summary == "OK",
              "suite_left_the_tree_as_found": tree == tree_before,
              "every_injection_ran_exactly_once": [row["id"] for row in injections] == names,
              "every_injection_compiles": all(
                  r["outcome"] != "INJECTION_DOES_NOT_COMPILE" for r in injections),
              "every_injection_caught": all(
                  r["outcome"] in ("CAUGHT", "CAUGHT_AT_FIXTURE") for r in injections),
              "every_copy_was_the_sealing_tree_when_made": all(at_start),
              "every_copy_was_the_sealing_tree_after_the_last_injection": all(at_end),
              "the_sealing_tree_is_unchanged_by_the_injections": sealing_at_end,
              "tree_restored_after_injections": restored,
              "creator_journal_as_found": _journal() == journal}
    # In the log before anything else can fail: the first parallel seal lost these when the
    # receipt could not be hashed.
    print("checks", json.dumps(checks), flush=True)
    body = {"record_type": "ISSUE_47_MODEL_EGRESS_OFFLINE_VERIFICATION",
            "requirement_id": "issue_47_v1", "all_checks_passed": all(checks.values()),
            "checks": checks, "calls": {"provider": 0, "paid": 0, "sec": 0},
            "suite": suite, "egress_gate": {
                "repository_transport_factories": gate["repository_transport_factories"],
                "egress_capability_references": gate["egress_capability_references"],
                "gate_receipt_id": gate["gate_receipt_id"]},
            "fault_injections": injections,
            "execution": {
                "mode": "PARALLEL_WORKER_COPIES",
                "contract": "docs/evidence/issue47_history/owner-decisions-2026-09-28/decisions.json",
                "copies": copy_names,
                "manifest": {"entries": len(tree), "digest": digest,
                             "scope": "every file and link under the tree, .git included, "
                                      "__pycache__ directories left out"},
                "order": "slow expected classes first (" + ", ".join(SLOW_FIRST) + "), then the "
                         "rest in list order; each injection ran once, in its own process, in "
                         "whichever copy was free - 'copy' in each row names it",
                "seconds": seconds},
            "creator_journal_at_start": journal,
            "generations_that_record_the_boundary_files": moved,
            "generation_manifests_measured": _generation_manifests(),
            "what_applying_the_patch_moves": (
                "every generation listed above records these files by bytes; those whose list "
                "is non-empty no longer validate their execution authority in a tree with the "
                "patch applied, so the patch cannot be applied beside them unchanged"),
            "bound_files": {path: _sha(path) for path in BOUND},
            "production_authorized": False, "live_call_authorized": False}
    receipt = {**body, "receipt_id": content_hash(value=body)}
    if not receipt["all_checks_passed"]:
        print(json.dumps(checks, indent=1))
        return 2
    (ROOT / OUTPUT).write_text(json.dumps(receipt, ensure_ascii=False, indent=1, sort_keys=True)
                               + "\n", encoding="utf-8")
    print(json.dumps({"receipt_id": receipt["receipt_id"], "checks": checks}, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt as interrupted:
        # The workers were stopped and the copies removed on the way out.
        print("INTERRUPTED_NO_RECEIPT:", interrupted, flush=True)
        sys.exit(2)
