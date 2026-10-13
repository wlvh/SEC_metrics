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
