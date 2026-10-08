"""Pure D02 Item 8 request and answer checks, shared by historical consumers.

This checks complete decisions and exact quotes against supplied blocks. It
neither judges legal scope nor calls a model, registers a Run or reads a trust
store. The existing V1 request, prompt and 20–300 character bounds are retained.
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


def quote_problem(*, quote, text, other_texts=()):
    """Return one form error, or None; never trim or rewrite a supplied quote.

    Match the raw block before testing length, so an invented long quote is
    not described as supported. A quote found only in another supplied block
    has a different cause from one found nowhere in the supplied text. Bounds
    count Python characters, as in the original V1 contract, not UTF-8 bytes.
    """
    if quote is None or (type(quote) is str and not quote):
        return "D02_REVIEW_QUOTE_MISSING"
    if type(quote) is not str:
        return "D02_REVIEW_QUOTE_WRONG_TYPE"
    if quote not in text:
        if any(quote in other for other in other_texts):
            return "D02_REVIEW_QUOTE_FROM_ANOTHER_BLOCK"
        return "D02_REVIEW_QUOTE_NOT_IN_BLOCK"
    lower = min(QUOTE_CHARACTERS[0], len(text.strip()))
    if len(quote) < lower:
        return "D02_REVIEW_QUOTE_TOO_SHORT"
    if len(quote) > QUOTE_CHARACTERS[1]:
        return "D02_REVIEW_QUOTE_TOO_LONG"
    return None


def _check_quote(*, quote, identity, texts):
    problem = quote_problem(quote=quote, text=texts[identity],
                            other_texts=(text for key, text in texts.items() if key != identity))
    if problem:
        raise LegalReviewContractError(problem + ":" + identity)


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
            _check_quote(quote=entry["quote"], identity=identity, texts=texts)
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
        _check_quote(quote=entry["quote"], identity=identity, texts=texts)
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


