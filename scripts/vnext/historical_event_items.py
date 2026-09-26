"""Read an 8-K item's own text for an event route's keyword confirmation.

E01's approved definition counts items 1.01, 2.01 and 8.01 and says of the last
"8.01 需正文关键词确认": an 8.01 counts once a keyword in its text confirms it.
The frozen matcher (``deterministic_router.match_event_claims``) compares the
declared aliases with each claim's ``brief``, and when the filing's hdr.sgml
carries item codes - every saved 8-K here - that brief is the program's own
sentence ``"8-K item 8.01 parsed from hdr.sgml"``. No alias can occur in it, so
the branch never admitted an 8.01 and never read one. The router is frozen by
every ``issue_28`` generation and the ordinary route uses it unchanged, so the
repair is carried here, for the historical routes only.

What this module owns is the reading, not the meaning. It locates the item in
the filing's primary document, reads its text from its heading to the next
item heading or the signatures, and records every alias the catalog declares
that occurs in that text, under the catalog's own normalisation and substring
match. The hdr brief is not consulted.

Whether an alias occurring in the item confirms it is the undecided part: the
approved substring rule says every occurrence does; read against the metric's
name, an occurrence in a use-of-proceeds list or a tender offer does not.
Until that meaning is decided the answer is kept to what does not depend on
it. The approved clause asks for keyword confirmation, so an item whose own
text carries no alias is not confirmed under any reading of that clause, and a
window whose keyword items all read that way is answered with the directly
counted items. A window where some keyword item's text does carry an alias is
withheld by name, with each occurrence recorded - neither reading is chosen by
default, and "must name a counterparty" is not adopted as the meaning here.

What the interim answer does not settle is a revision of the definition
itself. Counting "content-confirmed M&A announcements" would drop the keyword
requirement and ask the same of item 1.01, which the approved definition counts
directly: over the forty saved 8.01 items, three report a transaction the
registrant is party to with no declared alias in their text, and eleven of
the thirteen 1.01 items in the answered windows are borrowing agreements.
Values answered here are values under the approved definition; a revised one
is a new definition with its own results (docs/evidence/issue47_history/
e01-item-text/census.json and e01-keyword-branch/decision.json).

The heading is found in the frozen ``_visible_text`` view of the primary bytes,
so a reader can rebuild the same span from the same bytes. A heading is an
``Item x.yy`` occurrence followed by a capitalised word and not introduced by a
word that makes it a reference ("into this Item 2.03", "under Item 1.01") or by
an opening quotation mark. Consecutive headings of one item ("Item 5.02" then
"Item 5.02(b)") are one item. An item that cannot be located, or that is headed
twice with another item between, stops the answer by name: an unread item
never counts and never silently fails to count.

Not read: exhibits the item incorporates by reference. They are separate
documents, none of them is saved, and whether they belong to "8.01 正文" is
part of the scope question the decision has to settle; each item records
whether its own text incorporates an exhibit.
"""
import re

from .canonical import sha256_bytes
from .deterministic_router import _visible_text, normalize_event_text
from .sources import resolve_repository_file

RULE = "ITEM_TEXT_FROM_ITS_HEADING_TO_THE_NEXT_ITEM_HEADING_OR_THE_SIGNATURES"
TEXT_VIEW = "deterministic_router._visible_text"
INTERIM_POLICY = "AN_ALIAS_IN_A_KEYWORD_ITEM_S_OWN_TEXT_WITHHOLDS_UNTIL_ITS_MEANING_IS_DECIDED"
PENDING_REASON = "HISTORICAL_EVENT_KEYWORD_CONFIRMATION_MEANING_PENDING"
NOT_LOCATED_REASON = "HISTORICAL_EVENT_KEYWORD_ITEM_TEXT_NOT_LOCATED"

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
    signatures = _SIGNATURES.search(text, heading_end)
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
            "text_sha256": "sha256:" + sha256_bytes(content=body.encode("utf-8"))}


def alias_occurrences(*, text, aliases):
    """Every declared alias in ``text``, under the catalog's normalisation.

    Offsets are into the normalised text, which is what the match runs on and
    what ``normalized_sha256`` names.
    """
    normalised = normalize_event_text(value=text)
    found = []
    for alias in aliases:
        needle = normalize_event_text(value=alias)
        position = normalised.find(needle)
        while position >= 0:
            begin = normalised.rfind(". ", 0, position)
            finish = normalised.find(". ", position + len(needle))
            begin = 0 if begin < 0 else begin + 2
            finish = len(normalised) if finish < 0 else finish + 1
            if finish - begin > 2 * _CONTEXT:
                begin = max(begin, position - _CONTEXT)
                finish = min(finish, position + len(needle) + _CONTEXT)
            found.append({"alias": alias, "offset": position,
                          "sentence": normalised[begin:finish]})
            position = normalised.find(needle, position + 1)
    return normalised, sorted(found, key=lambda hit: (hit["offset"], hit["alias"]))


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


def keyword_item_answer(*, repo_root, route, claims, records):
    """Read each keyword item's own text and answer only what does not depend on its meaning.

    ``claims`` are the frozen adapter's item claims for the whole window and
    ``records`` the Run's source records, from which each primary document is
    read back by its reference and checked against its content hash.
    """
    keyword = {str(rule["item_code"]): [str(alias) for alias in rule["aliases"]]
               for rule in route["keyword_item_rules"]}
    direct = set(route["direct_item_codes"])
    _need(not direct & set(keyword), "EVENT_ROUTE_ITEM_CODE_IS_BOTH_DIRECT_AND_KEYWORD")
    items, pending, counted = [], [], []
    for claim in claims:
        attributes = claim["attributes"]
        code = str(attributes["item_code"])
        if code in direct:
            counted.append(claim["verified_claim_id"])
        if code not in keyword:
            continue
        reference, raw = _primary_bytes(repo_root=repo_root, records=records,
                                        reference_id=attributes["primary_source_reference_id"])
        _need(reference["accession"] == attributes["accession"],
              "EVENT_ITEM_PRIMARY_IS_ANOTHER_FILING", "SOURCE_INTEGRITY_ERROR")
        body = item_text(raw_bytes=raw, item_code=code)
        normalised, occurrences = alias_occurrences(text=body["text"], aliases=keyword[code])
        item = {"verified_claim_id": claim["verified_claim_id"],
                "accession": attributes["accession"], "item_code": code,
                "brief_source": attributes["brief_source"],
                "primary_source_reference_id": reference["source_reference_id"],
                "primary_raw_asset_id": reference["raw_asset_id"],
                "text_view": body["text_view"], "rule": body["rule"],
                "heading": body["heading"], "start": body["start"], "end": body["end"],
                "end_marker": body["end_marker"], "text_sha256": body["text_sha256"],
                "normalized_sha256": "sha256:" + sha256_bytes(content=normalised.encode("utf-8")),
                "alias_occurrences": occurrences,
                "incorporates_an_exhibit": bool(_EXHIBIT.search(body["text"])),
                "reading": ("ALIAS_IN_ITS_OWN_TEXT" if occurrences
                            else "NO_ALIAS_IN_ITS_OWN_TEXT")}
        items.append(item)
        if occurrences:
            pending.append(claim["verified_claim_id"])
    status = ("NO_KEYWORD_ITEM" if not items
              else "MEANING_PENDING" if pending else "NO_ALIAS_IN_ANY_KEYWORD_ITEM")
    return {"policy": INTERIM_POLICY, "rule": RULE, "keyword_item_codes": sorted(keyword),
            "items": items, "status": status, "pending_claim_ids": pending,
            "counted_claim_ids": counted,
            "not_read": "exhibits an item incorporates by reference; none is saved and "
                        "whether they belong to the item's text is part of the pending "
                        "scope question"}


def compact(answer):
    """The part a Run's observation binds: which items were read, where, and what they held."""
    return {"policy": answer["policy"], "rule": answer["rule"], "status": answer["status"],
            "items": [{**{key: item[key] for key in (
                "verified_claim_id", "item_code", "primary_source_reference_id",
                "primary_raw_asset_id", "text_view", "start", "end", "end_marker",
                "text_sha256", "normalized_sha256", "reading", "incorporates_an_exhibit")},
                "alias_offsets": [[hit["alias"], hit["offset"]]
                                  for hit in item["alias_occurrences"]]}
                for item in answer["items"]]}
