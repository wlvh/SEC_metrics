"""D02 Item 8 review: which blocks outside an incorporated note are litigation disclosures.

D02's approved source is Item 3, legal proceedings and contingencies notes. The
route takes Item 3 and every note an Item incorporates whole; the rest of the
financial statements (Item 8) reaches D02 only through a keyword, and the
keyword cannot tell a block that discloses a legal matter from one that
mentions litigation on the way to something else. Measured on the eleven
filings with a D02 set, it admits 24 Item 8 blocks, 5 of them wrongly, and
three deterministic replacements each fail on a real filing
(docs/evidence/issue47_history/d02-content-read/keyword-proxy-decision.json).
A review limited to what the keyword admits answers only half the question:
it cannot see a disclosure the keyword never admitted. So the review reads
every Item 8 block D02 could admit, under a contract the program checks:

* one request per filing, holding every such block's text exactly as the
  route read it, in document order;
* the answer decides every block that carries legal-process vocabulary - the
  keyword's admissions among them - exactly once, and lists any other block
  it counts, each with a quote that is an exact substring of that block;
* CANNOT_TELL_FROM_THE_TEXT is an answer, not a failure: a filing with a block
  its own text and neighbours do not settle is withheld by name, because
  publishing the settled part would report part of a set as the whole.

The vocabulary only decides which blocks must be answered explicitly. It does
not bound what is counted: any block in the request can be counted, so a
disclosure without a single legal word is still reachable. This module
decides nothing about a filing on its own; it builds the question, checks an
answer's form and says what a checked answer counts. It calls no model.
"""
import json
import re

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads

CONTRACT = "D02_ITEM_8_LEGAL_REVIEW_V1"
REQUEST_TYPE = "D02_ITEM_8_LEGAL_REVIEW_REQUEST"
DECISIONS = ("IN_SCOPE", "OUT_OF_SCOPE", "CANNOT_TELL_FROM_THE_TEXT")
# A quote is the part of the block the decision rests on, not a summary. A
# block shorter than the lower bound is quoted whole.
QUOTE_CHARACTERS = (20, 300)
WITHHELD_REASON = "HISTORICAL_D02_ITEM_8_REVIEW_DOES_NOT_SETTLE_IT"
REVIEW_LABEL = "ITEM_8_LEGAL_DISCLOSURE_BY_REGISTERED_REVIEW"
# Words that name a legal process or a claim. A block carrying one must be
# answered explicitly; every other block may still be counted.
MUST_DECIDE_TERMS = re.compile(
    r"(?i)\b(?:litigat\w*|lawsuits?|suits?|legal|proceedings?|claims?|courts?|settle\w*|"
    r"plaintiffs?|defendants?|complaints?|investigat\w*|subpoenas?|penalt\w*|fines?|"
    r"contingen\w*|arbitrat\w*|verdicts?|judgments?|alleg\w*|indemnif\w*)\b")
DEFINITION = {
    "source": "Item 3 / legal proceedings / contingencies notes "
              "(02_指标定义_SEC_10公司单年指标.md, D02)",
    "counts": "A block that discloses, for the registrant or one of its consolidated "
              "subsidiaries, a legal proceeding, lawsuit, arbitration, government investigation "
              "or enforcement action, or a claim - as defendant or as plaintiff; pending, "
              "threatened, settled or resolved - or a loss contingency, accrual or reserve "
              "arising from such matters, including the registrant's policy for recognizing or "
              "disclosing them; and a heading or continuation sentence of such a disclosure.",
    "does_not_count": "A block that mentions litigation or legal matters only on the way to "
                      "something else - for example the uncertainties behind accounting "
                      "estimates, legal fees as a cost policy, collection efforts on "
                      "receivables, transaction or financing costs, or debt covenant terms; "
                      "guarantees, purchase commitments or leases that involve no claim; "
                      "matters of another company unless the registrant or a subsidiary bears "
                      "the exposure; and the independent auditor's report."}
SYSTEM_PROMPT = (
    "You read blocks of the financial statements section (Item 8) of an SEC Form 10-K, in the "
    "order they appear in the filing. The request states under 'definition' which blocks are "
    "litigation disclosures and which are not; follow it exactly. Judge each block by its own "
    "text and the blocks around it: a heading or a continuation sentence belongs with the "
    "disclosure it introduces or continues. Decide every block listed under 'must_decide'. "
    "Then list under 'also_in_scope' every other block in 'blocks' that the definition counts. "
    "Answer CANNOT_TELL_FROM_THE_TEXT only when neither the block nor its neighbours say enough "
    "to decide; do not guess. Return one JSON object with exactly two keys: 'decisions', a list "
    "with exactly one entry per must_decide block, each {\"block_id\": <the block's id>, "
    "\"decision\": one of IN_SCOPE, OUT_OF_SCOPE, CANNOT_TELL_FROM_THE_TEXT, \"quote\": for "
    "IN_SCOPE and CANNOT_TELL_FROM_THE_TEXT the exact words of that block the decision rests on, "
    "copied character for character, between 20 and 300 characters or the whole text of a "
    "shorter block, and null for OUT_OF_SCOPE}; and 'also_in_scope', a list of {\"block_id\": "
    "<id>, \"quote\": the exact words, as above}, empty when there is none. Return nothing else.")


class LegalReviewContractError(ValueError):
    """A request or an answer that is not this contract's."""


class LegalReviewUnsettled(LegalReviewContractError):
    """A registered review that leaves a block undecided; the filing is withheld by name."""


def _need(condition, reason):
    if not condition:
        raise LegalReviewContractError(reason)


def block_id(index):
    """A block's id in the request: its position in the parsed filing."""
    return "b" + str(index)


def _texts_digest(blocks):
    return content_hash(value=[[block["block_id"], "sha256:" + sha256_bytes(
        content=block["text"].encode("utf-8"))] for block in blocks])


def review_request(*, company_id, target_cik, period_end, document, pool, keyword_admitted):
    """The request for one filing: every Item 8 block D02 could admit, and which must be decided.

    ``pool`` is the route's own list of Item 8 block indices outside every
    incorporated note, page furniture and the auditor's report
    (``historical_text_results.item_8_review_pool``), and ``keyword_admitted``
    the part of it the keyword admits today. The request's id is its content,
    so a changed text, a changed pool or a changed prompt is a different request.
    """
    _need(bool(pool) and list(pool) == sorted(set(pool)), "D02_REVIEW_POOL_INVALID")
    _need(set(keyword_admitted) <= set(pool), "D02_REVIEW_KEYWORD_OUTSIDE_THE_POOL")
    blocks = [{"block_id": block_id(index), "text": document["blocks"][index]["text"]}
              for index in pool]
    must = [block_id(index) for index in pool
            if index in set(keyword_admitted)
            or MUST_DECIDE_TERMS.search(document["blocks"][index]["text"])]
    filing = {"source_reference_id": document["source_reference_id"],
              "raw_asset_id": document["raw_asset_id"],
              "text_document_id": document["text_document_id"]}
    source = {"record_type": "D02_ITEM_8_REVIEW_SOURCE", "company_id": company_id,
              "period_end": period_end, "filing": filing, "texts": _texts_digest(blocks)}
    body = {"record_type": REQUEST_TYPE, "contract": CONTRACT, "metric_id": "D02",
            "company_id": company_id, "target_cik": str(target_cik), "period_end": period_end,
            "filing": filing, "definition": dict(DEFINITION), "blocks": blocks,
            "must_decide": must, "system_prompt": SYSTEM_PROMPT,
            "response_protocol": {"type": "D02_ITEM_8_DECISIONS_V1", "decisions": list(DECISIONS),
                                  "quote_characters": list(QUOTE_CHARACTERS)},
            "source_id": content_hash(value=source)}
    return {**body, "request_id": content_hash(value=body)}


def _quote_holds(quote, text):
    lower = min(QUOTE_CHARACTERS[0], len(text.strip()))
    return type(quote) is str and lower <= len(quote) <= QUOTE_CHARACTERS[1] and quote in text


def validate_answer(*, request, raw_output):
    """The decisions of an answer that passes the contract: (decisions, also_in_scope).

    Every check is on form, never on meaning: exactly the must-decide blocks,
    one decision each, a quote that is that block's own words where one is
    required and none where it is not, and additional blocks that are in the
    request, not already decided and named once.
    """
    _need(request.get("record_type") == REQUEST_TYPE and request.get("contract") == CONTRACT,
          "D02_REVIEW_REQUEST_IS_NOT_THIS_CONTRACT")
    try:
        answer = strict_json_loads(text=raw_output.decode("utf-8") if isinstance(raw_output, bytes)
                                   else raw_output)
    except (ValueError, UnicodeDecodeError) as error:
        raise LegalReviewContractError("D02_REVIEW_ANSWER_NOT_STRICT_JSON:" + str(error)[:80])
    _need(type(answer) is dict and set(answer) == {"decisions", "also_in_scope"}
          and type(answer["decisions"]) is list and type(answer["also_in_scope"]) is list,
          "D02_REVIEW_ANSWER_SHAPE")
    texts = {block["block_id"]: block["text"] for block in request["blocks"]}
    must = set(request["must_decide"])
    decisions = {}
    for entry in answer["decisions"]:
        _need(type(entry) is dict and set(entry) == {"block_id", "decision", "quote"},
              "D02_REVIEW_DECISION_SHAPE")
        identity = entry["block_id"]
        _need(identity in must, "D02_REVIEW_DECIDES_A_BLOCK_NOT_ASKED:" + str(identity)[:40])
        _need(identity not in decisions, "D02_REVIEW_BLOCK_DECIDED_TWICE:" + identity)
        _need(entry["decision"] in DECISIONS, "D02_REVIEW_DECISION_UNKNOWN:" + identity)
        if entry["decision"] == "OUT_OF_SCOPE":
            _need(entry["quote"] is None, "D02_REVIEW_OUT_OF_SCOPE_CARRIES_A_QUOTE:" + identity)
        else:
            _need(_quote_holds(entry["quote"], texts[identity]),
                  "D02_REVIEW_QUOTE_NOT_THE_BLOCKS_OWN_WORDS:" + identity)
        decisions[identity] = {"decision": entry["decision"], "quote": entry["quote"]}
    _need(set(decisions) == must, "D02_REVIEW_BLOCKS_UNDECIDED:"
          + ",".join(sorted(must - set(decisions)))[:200])
    added = {}
    for entry in answer["also_in_scope"]:
        _need(type(entry) is dict and set(entry) == {"block_id", "quote"},
              "D02_REVIEW_ADDITION_SHAPE")
        identity = entry["block_id"]
        _need(identity in texts, "D02_REVIEW_ADDS_A_BLOCK_NOT_IN_THE_REQUEST:" + str(identity)[:40])
        _need(identity not in must, "D02_REVIEW_ADDS_A_MUST_DECIDE_BLOCK:" + identity)
        _need(identity not in added, "D02_REVIEW_BLOCK_ADDED_TWICE:" + identity)
        _need(_quote_holds(entry["quote"], texts[identity]),
              "D02_REVIEW_QUOTE_NOT_THE_BLOCKS_OWN_WORDS:" + identity)
        added[identity] = {"quote": entry["quote"]}
    return decisions, added


def reviewed_blocks(*, request, decisions, added):
    """What a checked answer counts: (block ids in scope, withheld reason, unsettled ids).

    A filing with a block its text does not settle is withheld by name,
    whatever the rest says: the settled part is not the whole set.
    """
    unsettled = sorted(identity for identity, entry in decisions.items()
                       if entry["decision"] == "CANNOT_TELL_FROM_THE_TEXT")
    if unsettled:
        return None, WITHHELD_REASON, unsettled
    counted = {identity for identity, entry in decisions.items()
               if entry["decision"] == "IN_SCOPE"} | set(added)
    return [block["block_id"] for block in request["blocks"] if block["block_id"] in counted], None, []


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
