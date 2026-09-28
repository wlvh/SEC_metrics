"""Read an 8-K item's own text for E01's content-confirmed meaning.

E01's approved definition counts items 1.01, 2.01 and 8.01 and says of the last
"8.01 需正文关键词确认". The frozen matcher (``deterministic_router.
match_event_claims``) compares the declared aliases with each claim's
``brief``, and when the filing's hdr.sgml carries item codes - every saved 8-K
here - that brief is the program's own sentence ``"8-K item 8.01 parsed from
hdr.sgml"``, so no 8.01 was ever read. The router is frozen by every
``issue_28`` generation and the ordinary route uses it unchanged.

The owner's decision (recorded with the other owner decisions under
docs/evidence/issue47_history/) replaced the meaning for the historical route:
E01 counts content-confirmed M&A announcements - an item counts when its own
text reports a merger, acquisition, disposition or business combination the
registrant or a subsidiary is party to, whichever candidate code it is filed
under, and a keyword never confirms one. Over the forty saved 8.01 items a
keyword rule was right twice, wrong five times and missed three transactions,
and eleven of the thirteen 1.01 items in the answered windows are borrowing
agreements (docs/evidence/issue47_history/e01-item-text/census.json,
e01-keyword-branch/decision.json), so no item-code or keyword rule stands in
for the reading.

The successor route (catalog/r6/E01_content_confirmed_ma_v1.json) names the
approved route it replaces by hash, keeps the approved candidate codes, and
carries the confirmation meaning. What this module owns is reading each
candidate: it locates the item in the filing's primary document and reads its
text from its heading to the next item heading or the signatures, and binds
that span to its bytes, so a confirmation can be asked of exactly that span.
Nothing here confirms a candidate. A window with a candidate whose confirmation
is not registered is withheld by name, listing each candidate; a window with no
candidate item is answered zero. Values and acceptances under the approved
definition do not carry over: the successor route has its own hash, so its
Spec, and every acceptance bound to a Spec, is a different one.

The heading is found in the frozen ``_visible_text`` view of the primary bytes,
so a reader can rebuild the same span from the same bytes. A heading is an
``Item x.yy`` occurrence followed by a capitalised word and not introduced by a
word that makes it a reference ("into this Item 2.03", "under Item 1.01") or by
an opening quotation mark. Consecutive headings of one item ("Item 5.02" then
"Item 5.02(b)") are one item. An item that cannot be located, or that is headed
twice with another item between, stops the answer by name: an unread item
never counts and never silently fails to count.

Not read: exhibits the item incorporates by reference. They are separate
documents and none of them is saved; each candidate records whether its own
text incorporates an exhibit, so a confirmation that needs one says so.
Outside the candidate set: an announcement made only under another item (a
press release furnished under 7.01). The candidate codes are the approved
definition's; widening them would be a further change of meaning.
"""
import re

from pathlib import Path

from .canonical import content_hash, sha256_bytes, strict_json_loads
from .deterministic_router import _visible_text
from .sources import resolve_repository_file

RULE = "ITEM_TEXT_FROM_ITS_HEADING_TO_THE_NEXT_ITEM_HEADING_OR_THE_SIGNATURES"
TEXT_VIEW = "deterministic_router._visible_text"
CONFIRMATION_POLICY = "CONTENT_CONFIRMED_M_AND_A_ANNOUNCEMENT_V1"
CONFIRMATION_REASON = "HISTORICAL_E01_CONTENT_CONFIRMATION_NOT_REGISTERED"
NOT_LOCATED_REASON = "HISTORICAL_EVENT_ITEM_TEXT_NOT_LOCATED"
# A metric whose route the owner replaced, and the file that carries the
# successor. The frozen catalog keeps the approved route for the ordinary path
# and for every Run frozen under it.
SUCCESSOR_EVENT_ROUTES = {"E01": "catalog/r6/E01_content_confirmed_ma_v1.json"}
# The Spec each successor route compiles to, as the Markdown MetricSpec file a
# Run compiles its Specs from. Generated from the route by the ordinary set's
# own document writer (normal_run_specs._spec_document) and held to its bytes,
# so the file cannot say anything the route does not.
SUCCESSOR_SPEC_DOCUMENTS = {"E01": "catalog/r6/E01_content_confirmed_ma_v1.md"}

_HEADING = re.compile(
    r"(?<![A-Za-z])Items?\s*(\d{1,2}\.\d{2})(?:\([a-z]\))*\s*[.:\-\u2013\u2014]?\s*(?=[A-Z])")
# A reference is introduced by a word that points at an item, or by an opening
# quote around an item's title. A closed list of English function words, so
# nothing here names a filer; a checkbox glyph before a heading is not a word
# on this list, which is why the list is closed rather than "any lowercase".
_REFERENCE_BEFORE = re.compile(
    r"(?:\b(?:this|that|these|those|in|into|under|and|or|of|to|see|with|from|by|per|"
    r"pursuant|such|also)|[\u201c\u2018\"'])\s*$")
_SIGNATURES = re.compile(r"\bSIGNATURES?\b")
# Form 8-K's own captions for the items a successor route reads as candidates,
# and for the items filers most often head beside them. An item whose text is
# nothing but its caption, followed at once by another item's heading, is one
# whose content the filer wrote once under the headings together - Ford heads a
# credit-agreement amendment "Item 1.01 ... Item 2.03 ..." and writes it under
# 2.03 - so it shares the body that follows. The captions are the form's, not
# any filer's, and nothing is inferred from a caption that is not on this list.
_CAPTIONS = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.03": ("Creation of a Direct Financial Obligation or an Obligation under an "
             "Off-Balance Sheet Arrangement of a Registrant"),
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}
_LETTERS = re.compile(r"[^a-z]+")
_EXHIBIT = re.compile(r"\bExhibits?\s+\d+(?:\.\d+)?", re.I)
_CONTEXT = 240


class EventItemTextError(ValueError):
    """The item's own text could not be read; never a disclosure conclusion."""

    def __init__(self, reason, category="IMPLEMENTATION_GAP"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="IMPLEMENTATION_GAP"):
    if not condition:
        raise EventItemTextError(reason, category)


def item_headings(text):
    """(start, end, code) for every item heading, in document order."""
    found = []
    for match in _HEADING.finditer(text):
        if _REFERENCE_BEFORE.search(text[max(0, match.start() - 40):match.start()]):
            continue
        found.append((match.start(), match.end(), match.group(1)))
    return found


def item_text(*, raw_bytes, item_code):
    """The item's own text in the frozen visible-text view of ``raw_bytes``."""
    text = _visible_text(raw_bytes=raw_bytes)
    headings = item_headings(text)
    runs = []
    for heading in headings:
        if runs and runs[-1][-1][2] == heading[2]:
            runs[-1].append(heading)
        else:
            runs.append([heading])
    own = [run for run in runs if run[0][2] == item_code]
    _need(bool(own), "EVENT_ITEM_TEXT_NOT_LOCATED:" + item_code)
    _need(len(own) == 1, "EVENT_ITEM_HEADED_MORE_THAN_ONCE:" + item_code)
    start, heading_end, _ = own[0][0]
    later = [heading[0] for heading in headings if heading[0] > start and heading[2] != item_code]
    # Caption-only items share the body of the headings that follow them, as
    # far as each one in turn is caption-only too.
    shared, body_from = [], own[0][-1][1]
    following = [heading for heading in headings if heading[0] >= body_from]
    while (following and following[0][2] != item_code
           and _caption_only(text[body_from:following[0][0]], code=item_code if not shared
                             else shared[-1])):
        shared.append(following[0][2])
        body_from = following[0][1]
        following = following[1:]
        later = [heading[0] for heading in following if heading[2] != item_code]
    signatures = _SIGNATURES.search(text, heading_end if not shared else body_from)
    if later and (signatures is None or later[0] < signatures.start()):
        end, marker = later[0], "NEXT_ITEM_HEADING"
    elif signatures is not None:
        end, marker = signatures.start(), "SIGNATURES"
    else:
        end, marker = len(text), "END_OF_DOCUMENT"
    body = text[start:end]
    return {"item_code": item_code, "text_view": TEXT_VIEW, "rule": RULE,
            "start": start, "end": end, "end_marker": marker,
            "heading": text[start:heading_end].strip(), "text": body,
            "text_sha256": "sha256:" + sha256_bytes(content=body.encode("utf-8")),
            "shares_the_body_of": shared}


def _caption_only(gap, *, code):
    """True where ``gap`` - what follows an item's heading - is only that item's own caption."""
    caption = _CAPTIONS.get(code)
    return caption is not None and _LETTERS.sub("", gap.lower()) == _LETTERS.sub("", caption.lower())


def _primary_bytes(*, repo_root, records, reference_id):
    reference = records.get(reference_id)
    _need(reference is not None and reference["record_type"] == "SOURCE_REFERENCE",
          "EVENT_ITEM_PRIMARY_REFERENCE_ABSENT:" + str(reference_id), "SOURCE_INTEGRITY_ERROR")
    blob = records.get(reference["raw_asset_id"])
    _need(blob is not None and blob["record_type"] == "RAW_BLOB",
          "EVENT_ITEM_PRIMARY_BLOB_ABSENT:" + str(reference_id), "SOURCE_INTEGRITY_ERROR")
    raw = resolve_repository_file(repo_root=repo_root,
                                  repo_relative_path=blob["storage_uri"]).read_bytes()
    _need("sha256:" + sha256_bytes(content=raw) == reference["raw_asset_id"],
          "EVENT_ITEM_PRIMARY_BYTES_CHANGED:" + str(reference_id), "SOURCE_INTEGRITY_ERROR")
    return reference, raw


def successor_event_route(*, repo_root, metric_id, frozen_route):
    """The successor route for one metric, checked against the route it replaces.

    The record names its predecessor by route hash, so a successor written
    against a different approved route is refused rather than substituted. Its
    candidate codes are the codes it projects, and it has no keyword rules:
    under the content meaning a keyword never confirms an item.
    """
    record = strict_json_loads(text=(Path(repo_root) / SUCCESSOR_EVENT_ROUTES[metric_id]).read_text(
        encoding="utf-8"))
    _need(record.get("record_type") == "HISTORICAL_EVENT_ROUTE_SUCCESSOR" and record.get("metric_id") == metric_id,
          "HISTORICAL_EVENT_SUCCESSOR_ROUTE_INVALID:" + metric_id)
    _need(record["predecessor"]["route_hash"] == content_hash(value=dict(frozen_route)),
          "HISTORICAL_EVENT_SUCCESSOR_PREDECESSOR_CHANGED:" + metric_id)
    route = record["route"]
    _need(route["candidate_item_codes"] == route["direct_item_codes"] and not route["keyword_item_rules"]
          and route.get("confirmation", {}).get("policy") == CONFIRMATION_POLICY,
          "HISTORICAL_EVENT_SUCCESSOR_ROUTE_SHAPE_INVALID:" + metric_id)
    return route


def successor_public_notes(*, repo_root, metric_id):
    """What a public row under a successor route says its value means.

    The ordinary presentation policy's note for the metric describes the
    approved route's count, and that policy is bound by the issue_28
    generations, so the successor states its own meaning in its own file -
    beside the route, not inside it, so neither the route hash nor the Spec
    moves with the wording.
    """
    record = strict_json_loads(text=(Path(repo_root) / SUCCESSOR_EVENT_ROUTES[metric_id]).read_text(
        encoding="utf-8"))
    notes = record.get("public_notes")
    _need(type(notes) is str and notes.strip() == notes and bool(notes),
          "HISTORICAL_EVENT_SUCCESSOR_PUBLIC_NOTES_INVALID:" + metric_id)
    return notes


def content_confirmation_candidates(*, repo_root, route, claims, records, keep_text=False):
    """Every candidate item of a content-confirmed route, read from its own text.

    ``claims`` are the frozen adapter's item claims for the whole window and
    ``records`` the Run's source records, from which each primary document is
    read back by its reference and checked against its content hash. Nothing
    here confirms a candidate; it records where each one's own text is, so a
    confirmation can be asked of exactly that span and bound to its bytes.
    """
    _need(route["confirmation"]["policy"] == CONFIRMATION_POLICY,
          "EVENT_ROUTE_CONFIRMATION_POLICY_UNKNOWN:" + str(route["confirmation"].get("policy")))
    codes = [str(code) for code in route["candidate_item_codes"]]
    candidates = []
    for claim in claims:
        attributes = claim["attributes"]
        code = str(attributes["item_code"])
        if code not in codes:
            continue
        reference, raw = _primary_bytes(repo_root=repo_root, records=records,
                                        reference_id=attributes["primary_source_reference_id"])
        _need(reference["accession"] == attributes["accession"],
              "EVENT_ITEM_PRIMARY_IS_ANOTHER_FILING", "SOURCE_INTEGRITY_ERROR")
        body = item_text(raw_bytes=raw, item_code=code)
        candidates.append({"verified_claim_id": claim["verified_claim_id"],
                           "accession": attributes["accession"], "item_code": code,
                           "primary_source_reference_id": reference["source_reference_id"],
                           "primary_raw_asset_id": reference["raw_asset_id"],
                           "text_view": body["text_view"], "rule": body["rule"],
                           "heading": body["heading"], "start": body["start"], "end": body["end"],
                           "end_marker": body["end_marker"], "text_sha256": body["text_sha256"],
                           "characters": len(body["text"]),
                           "incorporates_an_exhibit": bool(_EXHIBIT.search(body["text"])),
                           "shares_the_body_of": body["shares_the_body_of"],
                           "confirmation": "NOT_REGISTERED",
                           # The text itself only where a confirmation request is
                           # built from it; a binding carries its hash.
                           **({"text": body["text"]} if keep_text else {})})
    return {"policy": CONFIRMATION_POLICY, "rule": RULE, "candidate_item_codes": codes,
            "candidates": candidates,
            "status": "CONFIRMATION_NOT_REGISTERED" if candidates else "NO_CANDIDATE_ITEM",
            "not_read": "exhibits an item incorporates by reference; none is saved"}


def compact_confirmation(answer):
    """The part a Run's observation binds: which candidates were read, and where."""
    return {"policy": answer["policy"], "rule": answer["rule"], "status": answer["status"],
            "candidate_item_codes": answer["candidate_item_codes"],
            "candidates": [{key: item[key] for key in (
                "verified_claim_id", "item_code", "primary_source_reference_id", "start", "end",
                "text_sha256", "confirmation")} for item in answer["candidates"]]}
