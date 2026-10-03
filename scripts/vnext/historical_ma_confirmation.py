"""E01 content confirmation: the question a model answers, and the checks its answer must pass.

The owner's E01 counts an announcement of a merger, acquisition, disposition or
business combination only once its content confirms it
(catalog/r6/E01_content_confirmed_ma_v1.json). Neither item codes nor keywords
can stand in for reading - measured on the saved filings, the keyword rule got
2 of 40 8.01 items right and 11 of 13 1.01 items in seven windows are borrowing
agreements (docs/evidence/issue47_history/e01-item-text/) - and a recorded
judgement per filing would be a manual input to every future update. So the
confirmation is a model's reading of each candidate item's own text, under a
contract the program checks:

* one request per fiscal-year window, holding every candidate item's text
  exactly as the route read it from the filing, each bound by SHA-256;
* the answer names every item exactly once, with one of three decisions, and a
  quote that is an exact substring of that item's text;
* CANNOT_TELL_FROM_THE_ITEM_TEXT is an answer, not a failure. Most candidate
  items incorporate an exhibit, and no exhibit is saved; an item that only
  points to one cannot be confirmed from its own text, and its window is
  withheld by name rather than guessed.

The count is the number of items confirmed as reporting a transaction, taken
over the candidates the route read. This module decides nothing on its own
about a filing: it builds the question, checks an answer's form, and says what
a checked answer counts. It calls no model.
"""
import json

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads

CONTRACT = "E01_CONTENT_CONFIRMATION_V1"
REQUEST_TYPE = "E01_CONTENT_CONFIRMATION_REQUEST"
DECISIONS = ("REPORTS_A_TRANSACTION", "DOES_NOT_REPORT_A_TRANSACTION",
             "CANNOT_TELL_FROM_THE_ITEM_TEXT")
# A quote is the part of the item the decision rests on, not a summary: long
# enough to carry a clause, short enough that it is a quotation.
QUOTE_CHARACTERS = (20, 600)
WITHHELD_REASON = "HISTORICAL_E01_ITEM_TEXT_DOES_NOT_SETTLE_IT"
SYSTEM_PROMPT = (
    "You read items of SEC Form 8-K filings. For each item, decide whether its own text "
    "reports a merger, acquisition, disposition or business combination - of a business, or "
    "of an equity stake in one - to which the registrant or one of its subsidiaries is a "
    "party, whether announced, agreed or completed. The request states, under 'definition', "
    "what counts and what does not; follow it exactly. Answer from the item text only. If the "
    "item only points to an exhibit or another document and its own text does not say enough "
    "to decide, answer CANNOT_TELL_FROM_THE_ITEM_TEXT; do not guess what the exhibit says. "
    "Return one JSON object with a key 'item_decisions': a list with exactly one entry per "
    "item in the request, each {\"item_id\": <the item's id>, \"decision\": one of "
    "REPORTS_A_TRANSACTION, DOES_NOT_REPORT_A_TRANSACTION, CANNOT_TELL_FROM_THE_ITEM_TEXT, "
    "\"quote\": the exact words of that item's text the decision rests on, copied character "
    "for character, between 20 and 600 characters}. Return nothing else.")


class ConfirmationContractError(ValueError):
    """A request or an answer that is not this contract's."""


def _need(condition, reason):
    if not condition:
        raise ConfirmationContractError(reason)


def item_id(candidate):
    """A candidate's id in the request: its filing, item code and the span it was read from."""
    return candidate["accession"] + "#" + candidate["item_code"] + "@" + str(candidate["start"])


def confirmation_request(*, route, company_id, target_cik, window, candidates):
    """The request for one window: every candidate item's text, and the route's definition.

    ``candidates`` are the route's own candidate records with the text the
    route read (``historical_event_items.content_confirmation_candidates``,
    with ``text`` kept). The request's id is its content, so a changed text, a
    changed definition or a changed set of items is a different request.
    """
    _need(bool(candidates), "E01_CONFIRMATION_REQUEST_HAS_NO_CANDIDATE")
    items = []
    for candidate in candidates:
        text = candidate["text"]
        _need("sha256:" + sha256_bytes(content=text.encode("utf-8")) == candidate["text_sha256"],
              "E01_CONFIRMATION_ITEM_TEXT_CHANGED:" + item_id(candidate))
        items.append({"item_id": item_id(candidate), "accession": candidate["accession"],
                      "item_code": candidate["item_code"],
                      "primary_source_reference_id": candidate["primary_source_reference_id"],
                      "heading": candidate["heading"], "text": text,
                      "text_sha256": candidate["text_sha256"]})
    _need(len({item["item_id"] for item in items}) == len(items), "E01_CONFIRMATION_ITEM_ID_REPEATS")
    definition = route["confirmation"]
    body = {"record_type": REQUEST_TYPE, "contract": CONTRACT, "metric_id": "E01",
            "company_id": company_id, "target_cik": str(target_cik),
            "window": {"period_start": window["period_start"], "period_end": window["period_end"]},
            "definition": {"counts": definition["counts"],
                           "does_not_count": definition["does_not_count"],
                           "unit": definition["unit"]},
            "items": items, "system_prompt": SYSTEM_PROMPT,
            "response_protocol": {"type": "E01_ITEM_DECISIONS_V1", "decisions": list(DECISIONS),
                                  "quote_characters": list(QUOTE_CHARACTERS)}}
    source = {"record_type": "E01_CONFIRMATION_SOURCE", "company_id": company_id,
              "window": body["window"], "items": [{key: item[key] for key in (
                  "item_id", "accession", "item_code", "primary_source_reference_id",
                  "text_sha256")} for item in items]}
    body["source_id"] = content_hash(value=source)
    body["request_id"] = content_hash(value={key: value for key, value in body.items()})
    return body


def validate_answer(*, request, raw_output):
    """The decisions of an answer that passes the contract, by item id.

    Every check is on form, never on meaning: exactly the request's items, one
    decision each from the three, a quote that is an exact substring of that
    item's text within the length bounds. Meaning is what the model was asked
    for; what the program can hold it to is that its answer is about these
    items, in these words.
    """
    _need(request.get("record_type") == REQUEST_TYPE and request.get("contract") == CONTRACT,
          "E01_CONFIRMATION_REQUEST_IS_NOT_THIS_CONTRACT")
    try:
        answer = strict_json_loads(text=raw_output.decode("utf-8") if isinstance(raw_output, bytes)
                                   else raw_output)
    except (ValueError, UnicodeDecodeError) as error:
        raise ConfirmationContractError("E01_CONFIRMATION_ANSWER_NOT_STRICT_JSON:" + str(error)[:80])
    _need(type(answer) is dict and set(answer) == {"item_decisions"}
          and type(answer["item_decisions"]) is list, "E01_CONFIRMATION_ANSWER_SHAPE")
    texts = {item["item_id"]: item["text"] for item in request["items"]}
    decisions = {}
    for entry in answer["item_decisions"]:
        _need(type(entry) is dict and set(entry) == {"item_id", "decision", "quote"},
              "E01_CONFIRMATION_DECISION_SHAPE")
        identity = entry["item_id"]
        _need(identity in texts, "E01_CONFIRMATION_ANSWERS_AN_ITEM_NOT_ASKED:" + str(identity)[:80])
        _need(identity not in decisions, "E01_CONFIRMATION_ITEM_ANSWERED_TWICE:" + identity)
        _need(entry["decision"] in DECISIONS, "E01_CONFIRMATION_DECISION_UNKNOWN:" + identity)
        quote = entry["quote"]
        _need(type(quote) is str and QUOTE_CHARACTERS[0] <= len(quote) <= QUOTE_CHARACTERS[1],
              "E01_CONFIRMATION_QUOTE_LENGTH:" + identity)
        _need(quote in texts[identity], "E01_CONFIRMATION_QUOTE_NOT_IN_THE_ITEM:" + identity)
        decisions[identity] = {"decision": entry["decision"], "quote": quote}
    _need(set(decisions) == set(texts), "E01_CONFIRMATION_ITEMS_UNANSWERED:"
          + ",".join(sorted(set(texts) - set(decisions)))[:200])
    return decisions


def confirmed_count(*, request, decisions):
    """What a checked answer counts: (value, reason, confirmed item ids).

    A window with an item its own text does not settle is withheld by name,
    whatever the other items say: counting the settled ones would report a
    lower bound as the count.
    """
    unsettled = sorted(identity for identity, entry in decisions.items()
                       if entry["decision"] == "CANNOT_TELL_FROM_THE_ITEM_TEXT")
    if unsettled:
        return None, WITHHELD_REASON, unsettled
    confirmed = [item["item_id"] for item in request["items"]
                 if decisions[item["item_id"]]["decision"] == "REPORTS_A_TRANSACTION"]
    return len(confirmed), None, confirmed


def request_bytes(request):
    """The canonical bytes a registration and a slot bind."""
    return canonical_json_bytes(value=request)


def provider_messages(request):
    """The chat messages: the fixed instruction, then the request without it."""
    payload = {key: value for key, value in request.items() if key != "system_prompt"}
    return [{"role": "system", "content": request["system_prompt"]},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":"))}]


# ------------------------------------------------------------------ registration

REQUIREMENT_ID = "issue_47_v1"
MODES = ("LIVE", "RECORDED_TEST_ONLY")
RECORD_TYPE = "ISSUE_47_HISTORICAL_REGISTERED_CONFIRMATION"
# The installed copy a Run reads, and the creator's journal it must match. The
# journal is D04's root with E01's own directory: inside the checkout's .git, so
# no data directory - and no Run - can write one.
EXPORT_PATH = "config/issue47_historical_ma_confirmation.json"
JOURNAL = ".git/issue47-historical-assessments"


def registered_confirmation(*, request, period_selection_id, output, mode, counted=None):
    """A registration: the answer to one window's request, checked, and what it counts.

    The record names the request it answers by id, so a changed text, a changed
    definition or a changed prompt is a different request and this record does
    not answer it. It keeps the assistant output itself, so every consumer can
    check the answer again under its own code. A LIVE one carries the counted
    call that answered it (``historical_counted_calls``): an independent review
    registered a LIVE confirmation with no call at all, and the batch published
    a withheld window as 3.
    """
    from .historical_counted_calls import check_counted_calls
    _need(mode in MODES, "E01_CONFIRMATION_MODE_INVALID")
    raw = output if isinstance(output, bytes) else output.encode("utf-8")
    _need(mode != "LIVE" or counted is not None, "E01_LIVE_CONFIRMATION_WITHOUT_COUNTED_CALLS")
    if counted is not None:
        check_counted_calls(counted=counted, answered=[(request, raw)], mode=mode)
    decisions = validate_answer(request=request, raw_output=raw)
    value, reason, items = confirmed_count(request=request, decisions=decisions)
    body = {"record_type": RECORD_TYPE, "schema_version": 1, "metric_id": "E01",
            "company_id": request["company_id"], "period_selection_id": period_selection_id,
            "source_id": request["source_id"], "request_id": request["request_id"],
            "contract": CONTRACT, "requirement_id": REQUIREMENT_ID, "mode": mode,
            "assistant_output": raw.decode("utf-8"), "decisions": decisions,
            "counted": {"value": value, "withheld_reason": reason, "items": items},
            "new_call_authority": False, "production_authorized": False}
    if counted is not None:
        body["counted_calls"] = counted
    return {**body, "input_record_id": content_hash(value=body)}


def validate_registered(*, record, request, period_selection_id, mode):
    """The record, if its answer re-derives under the current code for this request."""
    _need(type(record) is dict and record.get("record_type") == RECORD_TYPE
          and record.get("schema_version") == 1
          and record.get("input_record_id") == content_hash(value={
              key: value for key, value in record.items() if key != "input_record_id"}),
          "E01_CONFIRMATION_REGISTRATION_CHANGED")
    _need(record["requirement_id"] == REQUIREMENT_ID and record["mode"] == mode,
          "E01_CONFIRMATION_REGISTRATION_IS_FOR_ANOTHER_REQUIREMENT_OR_MODE")
    _need(record["request_id"] == request["request_id"],
          "E01_CONFIRMATION_REGISTERED_FOR_ANOTHER_REQUEST")
    again = registered_confirmation(request=request, period_selection_id=period_selection_id,
                                    output=record["assistant_output"], mode=mode,
                                    counted=record.get("counted_calls"))
    _need(again == record, "E01_CONFIRMATION_DOES_NOT_RE_DERIVE")
    if mode == "LIVE":
        from .historical_counted_calls import check_live_registration
        from .normal_source_authority import ROOT
        check_live_registration(counted=record.get("counted_calls"),
                                answered=[(request, record["assistant_output"].encode("utf-8"))],
                                repo_root=ROOT)
    return record


def journal_directory(*, mode, source_id):
    """Where the creator's own confirmations for one window's candidate set live."""
    from git_workspace import first_symlink_in_path
    from .normal_source_authority import ROOT
    _need(mode in MODES and str(source_id).startswith("sha256:"), "E01_CONFIRMATION_KEY_INVALID")
    git = ROOT / ".git"
    _need(git.is_dir() and not git.is_symlink(), "E01_CONFIRMATION_JOURNAL_REQUIRED")
    path = ROOT / JOURNAL / mode / "E01" / source_id[len("sha256:"):]
    _need(first_symlink_in_path(path=path) is None, "E01_CONFIRMATION_JOURNAL_ALIAS")
    return path


class ConfirmationNotRegistered(ConfirmationContractError):
    """No registered confirmation answers this window's request; a named withhold, not a failure."""


def load_registered_confirmation(*, data_root, request, period_selection_id, mode=None):
    """The registered confirmation a Run may consume for this window, checked again.

    D04's loader, for E01: from an installed data root the installed copy is
    read and its mode is the Run's; from the checkout that registered it, the
    creator journal is read, and where both exist they must be the same record.
    A LIVE copy must be in the creator journal; a RECORDED_TEST_ONLY one carries
    no credit and is consumed only when the caller or the installed copy names
    that mode - the default is LIVE, so a test registration never reaches a batch.
    """
    from pathlib import Path
    from .canonical import strict_json_file
    from .normal_source_authority import ROOT
    from .sources import resolve_repository_file
    export = Path(data_root) / EXPORT_PATH
    installed = (strict_json_file(path=resolve_repository_file(
        repo_root=data_root, repo_relative_path=EXPORT_PATH)) if export.exists() else None)
    if mode is None:
        mode = installed["mode"] if installed is not None else "LIVE"
    _need(mode in MODES, "E01_CONFIRMATION_MODE_INVALID")
    _need(installed is None or installed.get("mode") == mode, "E01_CONFIRMATION_MODE_CONFLICT")
    directory = (journal_directory(mode=mode, source_id=request["source_id"])
                 if (ROOT / ".git").is_dir() else None)
    if installed is None:
        choices = sorted(directory.glob("*.json")) if directory is not None and directory.is_dir() else []
        matching = [path for path in choices
                    if strict_json_file(path=path).get("request_id") == request["request_id"]]
        if not matching:
            raise ConfirmationNotRegistered("E01_CONFIRMATION_NOT_REGISTERED:" + mode
                                            + (":ONLY_FOR_ANOTHER_REQUEST" if choices else ""))
        _need(len(matching) == 1, "E01_CONFIRMATION_REGISTRATION_AMBIGUOUS:" + mode)
        record = strict_json_file(path=matching[0])
    else:
        record = installed
        path = (directory / (str(record.get("input_record_id", ""))[len("sha256:"):] + ".json")
                if directory is not None else None)
        if path is not None and path.is_file():
            _need(strict_json_file(path=path) == record, "E01_CONFIRMATION_INSTALLED_COPY_CHANGED")
        else:
            _need(mode == "RECORDED_TEST_ONLY", "E01_LIVE_CONFIRMATION_NOT_IN_CREATOR_JOURNAL")
    return validate_registered(record=record, request=request,
                               period_selection_id=period_selection_id, mode=mode)


def register_confirmation(*, request, period_selection_id, output, mode, counted=None):
    """Write a checked confirmation into the creator journal; the same bytes again is a no-op."""
    from sec_http import write_immutable_bytes
    from .native_unit_index import evidence_json_bytes
    record = registered_confirmation(request=request, period_selection_id=period_selection_id,
                                     output=output, mode=mode, counted=counted)
    directory = journal_directory(mode=mode, source_id=request["source_id"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (record["input_record_id"][len("sha256:"):] + ".json")
    write_immutable_bytes(path=path, content=evidence_json_bytes(record))
    return record, path


# --------------------------------------------------------- the invocation acceptance

def build_acceptance(*, request, source_reference_ids, plan, response_body, spec_semantic_hash):
    """The Candidate and Evidence a successful call must carry, for the WB-3 acceptance receipt.

    The same shape the native semantic routes give the controller
    (capacity_native_assessment._build_acceptance): an OBSERVATION_CANDIDATE
    holding the checked decisions and what they count, and an EVIDENCE_CHECK
    naming the two checks an answer passed - every item answered once, and
    every quote the item's own words. A call whose answer fails either is not
    a success; the controller records it as an evidence failure.
    """
    from pathlib import Path
    from .canonical import sha256_file
    from .records import validate_record
    decisions = validate_answer(request=request, raw_output=response_body)
    value, reason, items = confirmed_count(request=request, decisions=decisions)
    _need(bool(source_reference_ids) and len(set(source_reference_ids)) == len(source_reference_ids),
          "E01_CONFIRMATION_SOURCE_REFERENCES_INVALID")
    selected = {"content_confirmation": {"request_id": request["request_id"],
                                         "item_ids": [item["item_id"] for item in request["items"]],
                                         "decisions": decisions,
                                         "counted": {"value": value, "withheld_reason": reason,
                                                     "items": items}}}
    body = {"disclosure_group": "e01_content_confirmation_v1",
            "source_reference_ids": list(source_reference_ids),
            "derived_asset_ids": [plan["selected_representation_hash"]], "selected": selected,
            "competing_candidates": [], "unresolved_competing_claims": []}
    candidate = validate_record(record={
        "record_type": "OBSERVATION_CANDIDATE", **body, "candidate_hash": content_hash(value=body),
        "attempt_id": "ma-confirmation:" + plan["ai_invocation_plan_id"][7:],
        "assistant_output_sha256": sha256_bytes(content=response_body), "status": "CANDIDATE"})
    evidence_body = {"candidate_hash": candidate["candidate_hash"], "status": "PASS",
                     "normalized_values": selected,
                     "checks": [{"check": "E01_EVERY_ITEM_ANSWERED_ONCE", "status": "PASS",
                                 "request_id": request["request_id"],
                                 "item_ids": selected["content_confirmation"]["item_ids"]},
                                {"check": "E01_QUOTES_ARE_THE_ITEMS_OWN_WORDS", "status": "PASS",
                                 "decisions": decisions}],
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
