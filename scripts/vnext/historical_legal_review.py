"""Historical D02 review registration and consumers.

Request construction, quote diagnostics and answer form live in the shared
``legal_review_contract`` module. This historical adapter retains its existing
registration and Run interpretation; it does not change old answers or failures.
"""
from .canonical import canonical_json_bytes, content_hash, sha256_bytes
from .legal_review_contract import (
    CONTRACT, REQUEST_TYPE, DECISIONS, QUOTE_CHARACTERS, WITHHELD_REASON,
    REVIEW_LABEL, MUST_DECIDE_TERMS, DEFINITION, SYSTEM_PROMPT,
    LegalReviewContractError, LegalReviewUnsettled, _need, block_id,
    review_request, quote_problem, validate_answer, reviewed_blocks,
    request_bytes, provider_messages,
)


# ------------------------------------------------------------------ registration

REQUIREMENT_ID = "issue_47_v1"
MODES = ("LIVE", "RECORDED_TEST_ONLY")
RECORD_TYPE = "ISSUE_47_HISTORICAL_REGISTERED_D02_REVIEW"
# The installed copy a Run reads, and the creator's journal it must match - the
# same root as D04's and E01's, inside the checkout's .git, so no data
# directory and no Run can write one.
EXPORT_PATH = "config/issue47_historical_legal_review.json"
JOURNAL = ".git/issue47-historical-assessments"


def review_key(*, company_id, period_selection_id, raw_asset_id):
    """The position a review answers: one company, one pinned period, one filing's bytes.

    Known before the request is built, so a text input can find the reviews of
    its position without parsing the filing; which of them answers today's
    request is decided when the request is rebuilt.
    """
    return content_hash(value={"metric_id": "D02", "company_id": company_id,
                               "period_selection_id": period_selection_id,
                               "raw_asset_id": raw_asset_id})


def registered_review(*, request, company_id, period_selection_id, output, mode, counted=None):
    """A registration: one filing's answer, checked, and what it counts.

    The record names the request by id, so a changed block, pool or prompt is a
    different request this record does not answer. It keeps the assistant
    output itself, so every consumer can check the answer again under its own
    code. A LIVE one carries the counted call that answered it
    (``historical_counted_calls``): an independent review registered a LIVE
    review with no call at all, and the batch's default loader read it.
    """
    from .historical_counted_calls import check_counted_calls
    _need(mode in MODES, "D02_REVIEW_MODE_INVALID")
    _need(request["company_id"] == company_id, "D02_REVIEW_IS_FOR_ANOTHER_COMPANY")
    raw = output if isinstance(output, bytes) else output.encode("utf-8")
    _need(mode != "LIVE" or counted is not None, "D02_LIVE_REVIEW_WITHOUT_COUNTED_CALLS")
    if counted is not None:
        check_counted_calls(counted=counted, answered=[(request, raw)], mode=mode)
    decisions, added = validate_answer(request=request, raw_output=raw)
    in_scope, reason, unsettled = reviewed_blocks(request=request, decisions=decisions, added=added)
    body = {"record_type": RECORD_TYPE, "schema_version": 1, "metric_id": "D02",
            "company_id": company_id, "period_selection_id": period_selection_id,
            "review_key": review_key(company_id=company_id, period_selection_id=period_selection_id,
                                     raw_asset_id=request["filing"]["raw_asset_id"]),
            "source_id": request["source_id"], "request_id": request["request_id"],
            "contract": CONTRACT, "requirement_id": REQUIREMENT_ID, "mode": mode,
            "assistant_output": raw.decode("utf-8"), "decisions": decisions, "added": added,
            "reviewed": {"in_scope": in_scope, "withheld_reason": reason, "unsettled": unsettled},
            "new_call_authority": False, "production_authorized": False}
    if counted is not None:
        body["counted_calls"] = counted
    return {**body, "input_record_id": content_hash(value=body)}


def _record_holds(record):
    return (type(record) is dict and record.get("record_type") == RECORD_TYPE
            and record.get("schema_version") == 1
            and record.get("input_record_id") == content_hash(value={
                key: value for key, value in record.items() if key != "input_record_id"}))


def select_registered_review(*, records, request):
    """The record among a position's reviews that answers this request, re-derived.

    None when the position has no review. A position whose reviews all answer
    another request - the pool, a block's text or the prompt changed since -
    is refused by name rather than read as unreviewed: a review exists, and
    quietly falling back to the keyword would hide that it no longer holds.
    """
    if not records:
        return None
    matching = [record for record in records if record.get("request_id") == request["request_id"]]
    _need(bool(matching), "D02_REVIEW_REGISTERED_FOR_ANOTHER_REQUEST")
    _need(len(matching) == 1, "D02_REVIEW_REGISTRATION_AMBIGUOUS")
    record = matching[0]
    _need(_record_holds(record) and record["requirement_id"] == REQUIREMENT_ID
          and record["mode"] in MODES, "D02_REVIEW_REGISTRATION_CHANGED")
    again = registered_review(request=request, company_id=record["company_id"],
                              period_selection_id=record["period_selection_id"],
                              output=record["assistant_output"], mode=record["mode"],
                              counted=record.get("counted_calls"))
    _need(again == record, "D02_REVIEW_DOES_NOT_RE_DERIVE")
    if record["mode"] == "LIVE":
        from .historical_counted_calls import check_live_registration
        from .normal_source_authority import ROOT
        check_live_registration(counted=record.get("counted_calls"),
                                answered=[(request, record["assistant_output"].encode("utf-8"))],
                                repo_root=ROOT)
    return record


def journal_directory(*, mode, key):
    """Where the creator's own reviews for one position live."""
    from git_workspace import first_symlink_in_path
    from .normal_source_authority import ROOT
    _need(mode in MODES and str(key).startswith("sha256:"), "D02_REVIEW_KEY_INVALID")
    git = ROOT / ".git"
    _need(git.is_dir() and not git.is_symlink(), "D02_REVIEW_JOURNAL_REQUIRED")
    path = ROOT / JOURNAL / mode / "D02" / key[len("sha256:"):]
    _need(first_symlink_in_path(path=path) is None, "D02_REVIEW_JOURNAL_ALIAS")
    return path


def load_registered_reviews(*, data_root, company_id, period_selection_id, raw_asset_id,
                            mode=None):
    """Every review registered for this position that a Run may consume; no request yet.

    E01's loader, for D02, with one difference: the request is not known here,
    so this returns the position's records and ``select_registered_review``
    picks the one answering the rebuilt request. From an installed data root
    the installed copy is read and its mode is the Run's; from the checkout
    that registered it, the creator journal is read. A LIVE copy must be in the
    creator journal; a RECORDED_TEST_ONLY one carries no credit and is read only
    when the caller or the installed copy names that mode - the default is LIVE.
    """
    from pathlib import Path
    from .canonical import strict_json_file
    from .normal_source_authority import ROOT
    from .sources import resolve_repository_file
    data_root = Path(data_root)
    key = review_key(company_id=company_id, period_selection_id=period_selection_id,
                     raw_asset_id=raw_asset_id)
    export = data_root / EXPORT_PATH
    installed = (strict_json_file(path=resolve_repository_file(
        repo_root=data_root, repo_relative_path=EXPORT_PATH)) if export.exists() else None)
    if mode is None:
        mode = installed["mode"] if installed is not None else "LIVE"
    _need(mode in MODES, "D02_REVIEW_MODE_INVALID")
    _need(installed is None or installed.get("mode") == mode, "D02_REVIEW_MODE_CONFLICT")
    directory = journal_directory(mode=mode, key=key) if (ROOT / ".git").is_dir() else None
    if installed is None:
        choices = sorted(directory.glob("*.json")) if directory is not None and directory.is_dir() else []
        records = [strict_json_file(path=path) for path in choices]
    else:
        _need(installed.get("review_key") == key, "D02_REVIEW_INSTALLED_FOR_ANOTHER_POSITION")
        path = (directory / (str(installed.get("input_record_id", ""))[len("sha256:"):] + ".json")
                if directory is not None else None)
        if path is not None and path.is_file():
            _need(strict_json_file(path=path) == installed, "D02_REVIEW_INSTALLED_COPY_CHANGED")
        else:
            _need(mode == "RECORDED_TEST_ONLY", "D02_LIVE_REVIEW_NOT_IN_CREATOR_JOURNAL")
        records = [installed]
    for record in records:
        _need(_record_holds(record) and record["review_key"] == key and record["mode"] == mode
              and record["requirement_id"] == REQUIREMENT_ID, "D02_REVIEW_REGISTRATION_CHANGED")
    return records


def register_review(*, request, company_id, period_selection_id, output, mode, counted=None):
    """Write a checked review into the creator journal; the same bytes again is a no-op."""
    from sec_http import write_immutable_bytes
    from .native_unit_index import evidence_json_bytes
    record = registered_review(request=request, company_id=company_id,
                               period_selection_id=period_selection_id, output=output, mode=mode,
                               counted=counted)
    directory = journal_directory(mode=mode, key=record["review_key"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (record["input_record_id"][len("sha256:"):] + ".json")
    write_immutable_bytes(path=path, content=evidence_json_bytes(record))
    return record, path


# --------------------------------------------------------- the invocation acceptance

def build_acceptance(*, request, source_reference_ids, plan, response_body, spec_semantic_hash):
    """The Candidate and Evidence a successful call must carry, for the WB-3 acceptance receipt.

    E01's shape: an OBSERVATION_CANDIDATE holding the checked decisions and
    what they count, and an EVIDENCE_CHECK naming the two checks an answer
    passed - every must-decide block answered once, and every quote the
    block's own words. A call whose answer fails either is not a success; the
    controller records it as an evidence failure.
    """
    from pathlib import Path
    from .canonical import sha256_file
    from .records import validate_record
    decisions, added = validate_answer(request=request, raw_output=response_body)
    counted, reason, unsettled = reviewed_blocks(request=request, decisions=decisions, added=added)
    _need(bool(source_reference_ids) and len(set(source_reference_ids)) == len(source_reference_ids),
          "D02_REVIEW_SOURCE_REFERENCES_INVALID")
    selected = {"item_8_review": {"request_id": request["request_id"],
                                  "must_decide": list(request["must_decide"]),
                                  "decisions": decisions, "added": added,
                                  "reviewed": {"in_scope": counted, "withheld_reason": reason,
                                               "unsettled": unsettled}}}
    body = {"disclosure_group": "d02_item_8_legal_review_v1",
            "source_reference_ids": list(source_reference_ids),
            "derived_asset_ids": [plan["selected_representation_hash"]], "selected": selected,
            "competing_candidates": [], "unresolved_competing_claims": []}
    candidate = validate_record(record={
        "record_type": "OBSERVATION_CANDIDATE", **body, "candidate_hash": content_hash(value=body),
        "attempt_id": "legal-review:" + plan["ai_invocation_plan_id"][7:],
        "assistant_output_sha256": sha256_bytes(content=response_body), "status": "CANDIDATE"})
    evidence_body = {"candidate_hash": candidate["candidate_hash"], "status": "PASS",
                     "normalized_values": selected,
                     "checks": [{"check": "D02_EVERY_MUST_DECIDE_BLOCK_ANSWERED_ONCE", "status": "PASS",
                                 "request_id": request["request_id"],
                                 "must_decide": list(request["must_decide"])},
                                {"check": "D02_QUOTES_ARE_THE_BLOCKS_OWN_WORDS", "status": "PASS",
                                 "decisions": decisions, "added": added}],
                     "reason_codes": [], "identity_constraints": []}
    evidence = validate_record(record={"record_type": "EVIDENCE_CHECK", **evidence_body,
                                       "evidence_check_id": content_hash(value=evidence_body)})
    return {"candidate_hash": candidate["candidate_hash"], "candidate_record": candidate,
            "derived_asset_id": plan["selected_representation_hash"],
            "evidence_candidate_hash": candidate["candidate_hash"],
            "evidence_check_id": evidence["evidence_check_id"], "evidence_record": evidence,
            "evidence_status": "PASS", "reader_input_manifest_id": plan["source_identity_hash"],
            "source_reference_ids": list(source_reference_ids),
            "spec_semantic_hash": spec_semantic_hash, "task_contract_hash": plan["task_contract_hash"],
            "validator_semantic_hash": content_hash(value={
                "module": sha256_file(path=Path(__file__)), "contract": CONTRACT}),
            "validator_semantic_version": CONTRACT}
