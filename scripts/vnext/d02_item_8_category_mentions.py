"""D02, Item 8: a paragraph that names litigation only as a category.

D02's source is Item 3, the notes it incorporates, and contingencies notes.
Item 8 at large is not, so the route lets an Item 8 paragraph in only when the
legal keyword occurs in it (``text_business_candidates`` pattern ``legal``).
That keyword admits wherever the word stands: readers judged 20 of the 85
admissions they read, in the eleven latest and the thirty older filings, to be
no disclosure of a legal matter of the registrant. Every one of the twenty has
the same two properties, and none of the 65 disclosures has both:

* each occurrence of the keyword is one item of a coordinated list ("finance,
  regulatory, litigation, and other matters"; "competition, litigation,
  legislation"; "litigation and environmental reserves"; "administrative and
  legal proceedings") or an example in a parenthetical ("(including
  litigation, where appropriate)");
* nothing in the paragraph states a legal matter of the registrant: it is not
  said to be subject to, involved in or a party to one, it accrues or records
  nothing for one, and no filing, court, allegation, ruling, party or
  settlement of a matter appears.

A paragraph with both properties leaves D02's Item 8 set; any other keyword
paragraph stays. The rule only removes, so a disclosure the keyword never
admitted is still outside the set - the other direction is the review pool's
(``historical_text_results.item_8_review_pool``).

What counts as a list (version 2 of the terms). Version 1 took any separator
beside the word as list evidence, so a comma that opens a relative clause or a
participial phrase counted: "We face litigation, which could result in a
significant loss." and "Litigation, brought by a customer against us in 2025,
remains unresolved." were left out (#28's review of the rule's first wiring,
Issue #47 comment 5948676381). Version 2 keeps version 1's evidence - so it can
only keep more than version 1, never less - and requires the structure that
evidence has to stand in, read from closed-class words only:

* the keyword's own phrase is no clause (no auxiliary, modal or copula, no
  relative or subordinating word, no "we") and names no party ("brought by",
  "against") and not the registrant ("our", "us", "the Company");
* the phrase is not the first item of its sentence - a keyword there is the
  sentence's subject or the direct object of its own verb ("We face
  litigation, ...");
* it is coordinated with another list item: walking across the separators
  around it, through items that are no clause, a coordinator (and, or, as well
  as) is crossed; or it is an example after "including"/"such as", or in a
  parenthetical that opens with one;
* the series is not the subject of a predicate - no item right after it opens
  with a clause word ("..., remains unresolved");
* the series is not governed by the registrant as subject - its governing item
  does not open with "we" or "the Company" without a preposition ("We face
  regulatory actions, litigation and fines").

What has to be proven (version 3 of the terms). Version 2 left out "During
2025, our company faced litigation, regulatory proceedings and fines." (#28's
scoped review of its copy, 79677ed2, NEEDS_FIX P2): it knew the registrant only
as "we" or "the Company" at the start of an item, the fronted "During 2025,"
put the keyword after a comma, and no relation read "faced". Each gap could be
closed by one more word, and the next sentence would need another. So version 3
asks for proof: it runs version 2's decision unchanged and, only where version
2 reads a category, requires more before it agrees - a block version 2 keeps
cannot leave, by construction. A sentence the closed-class words cannot place
stays:

* the keyword opens its own item, apart from a determiner ("other
  litigation"); words before it in the item - "our company faced", "two
  putative class-action" - may be its own subject and verb, which closed-class
  words cannot tell from a modifier; and the registrant acting ("we", "the"
  or "our" + company, firm, corporation, registrant) before it in the item
  governs it;
* where the registrant is named before the keyword in its sentence, the series
  must hang on a closed-class governor: a preposition, "including" or "such
  as" before the series' first member ("advise us on finance, regulatory,
  litigation and other matters"), not one opening the sentence ("In our
  business, ..."). The series is found by walking across plain items, and an
  item naming the registrant acting is not one. Then the nearest subject or
  object reference to the registrant before the governor must not be the
  registrant acting in the same clause: "us" in "advise us on" is the one
  advised, while "our company was hit with regulatory proceedings, litigation
  and fines" is its own matter; a relative or subordinating word between the
  two puts them in different clauses ("We are subject to risks that may cause
  results to differ, such as competition, litigation, ..."). A possessive
  ("our business") is neither subject nor object;
* an example ("such as litigation") or a parenthetical example ("(including
  litigation)") is asked the same of the text before its marker, including the
  sentence before the parenthetical;
* facing a legal matter joins the relations that state one ("faced
  litigation").

What it decides from and what it does not. A list member is read from the
words around it, not from what the list is about; the paragraph's
legal-matter vocabulary is read anywhere in the block, so a paragraph that says
"pending" or "accrued" about something else stays in (the cautious direction:
it can keep a paragraph a reader would leave out, and cannot drop one a reader
would keep for the reasons it reads). Open-class words are not read: a series
in subject position whose verb is attached to its last item ("In 2025,
litigation, fines and penalties increased.") still reads as a list, and a
matter stated in words outside the vocabulary is not seen. A block that is not
prose - no sentence punctuation, such as a heading "Litigation and Regulatory
Matters" - is never removed: a label names what follows rather than listing a
category. A self-insurance paragraph shows why the two properties must hold
together: its keyword is a list member ("losses, settlements, litigation costs
and other factors") and it is a disclosure, because the registrant accrues for
its own claims. The vocabulary lives in
``catalog/r6/D02_item_8_category_mention_v3.json``; versions 1 and 2 keep their
bytes as history.
"""
from __future__ import annotations

import re
from pathlib import Path

from .canonical import content_hash, strict_json_file

RECORD_TYPE = "D02_ITEM_8_CATEGORY_MENTION_TERMS"
_TERMS_PATH = Path(__file__).resolve().parents[2] / "catalog/r6/D02_item_8_category_mention_v3.json"
_MENTION_KEYS = {"separator_before", "separator_after", "parenthetical_example", "example_before",
                 "prose", "sentence_boundary", "series_separator", "coordinator", "clause_word",
                 "clause_starter", "first_person_subject", "party_preposition",
                 "registrant_reference", "registrant_subject", "preposition",
                 "registrant_actor", "head_determiner"}


class CategoryMentionTermsError(ValueError):
    """The vocabulary file is not the one this module reads."""


# The anchored clause-starter pattern opens with this; version 3 also reads its
# words anywhere, from the same list.
_OPENING = "^\\W*"


def _load(path):
    terms = strict_json_file(path=path)
    if (type(terms) is not dict or terms.get("record_type") != RECORD_TYPE
            or terms.get("schema_version") != 3 or terms.get("metric_id") != "D02"
            or type(terms.get("category_mention")) is not dict
            or set(terms["category_mention"]) != _MENTION_KEYS
            or type(terms.get("exposure")) is not list or not terms["exposure"]
            or any(type(item) is not dict or set(item) != {"name", "pattern", "why"}
                   for item in terms["exposure"])
            or len({item["name"] for item in terms["exposure"]}) != len(terms["exposure"])
            or not terms["category_mention"]["clause_starter"].startswith(_OPENING)):
        raise CategoryMentionTermsError("D02_CATEGORY_MENTION_TERMS_INVALID:" + str(path))
    return terms


_TERMS = _load(_TERMS_PATH)
TERMS_HASH = content_hash(value=_TERMS)
_MENTION = {name: re.compile(pattern, re.I)
            for name, pattern in _TERMS["category_mention"].items()}
_EXPOSURE = tuple((item["name"], re.compile(item["pattern"], re.I))
                  for item in _TERMS["exposure"])
# A clause word opening an item: the item is a predicate, not a list member.
_OPENS_WITH_CLAUSE_WORD = re.compile(r"^\W*" + _TERMS["category_mention"]["clause_word"], re.I)
# A relative or subordinating word anywhere: it starts a clause.
_CLAUSE_STARTER_WORD = re.compile(
    r"\b" + _TERMS["category_mention"]["clause_starter"][len(_OPENING):], re.I)


def _parenthetical_example(text, start):
    """The occurrence sits in an open parenthetical that begins "(including" or "(such as"."""
    opened = text.rfind("(", 0, start)
    if opened < 0 or text.rfind(")", 0, start) > opened:
        return False
    return bool(_MENTION["parenthetical_example"].search(text[opened:start]))


def _list_member(text, start, end):
    """A list separator stands right before or right after the occurrence (version 1's evidence)."""
    return bool(_MENTION["separator_before"].search(text[max(0, start - 40):start])
                or _MENTION["separator_after"].search(text[end:end + 12]))


def _sentence(text, start, end):
    """Where the sentence around an occurrence begins and ends."""
    begin, finish = 0, len(text)
    for boundary in _MENTION["sentence_boundary"].finditer(text):
        if boundary.end() <= start:
            begin = boundary.end()
        elif boundary.start() >= end:
            finish = boundary.start()
            break
    return begin, finish


def _segment(text, start, end):
    """The text a series lives in, as (offset, text).

    The sentence around the occurrence, or the innermost parenthetical it is
    open in. Outside, parentheticals are blanked so their separators do not
    join the series around them.
    """
    begin, finish = _sentence(text, start, end)
    opened = text.rfind("(", begin, start)
    if opened >= 0 and text.rfind(")", opened, start) < 0:
        close = text.find(")", end, finish)
        inner = opened + 1, (close if close >= 0 else finish)
        return inner[0], text[inner[0]:inner[1]]
    chars, depth = list(text[begin:finish]), 0
    for index, char in enumerate(chars):
        if char == "(":
            depth += 1
        if depth:
            chars[index] = " "
        if char == ")" and depth:
            depth -= 1
    return begin, "".join(chars)


def _items(segment):
    """The segment split at separators: [(item, start, end), (separator, coordinates), ...]."""
    parts, position = [], 0
    for separator in _MENTION["series_separator"].finditer(segment):
        parts.append((segment[position:separator.start()], position, separator.start()))
        parts.append((separator.group(0), bool(_MENTION["coordinator"].search(separator.group(0)))))
        position = separator.end()
    parts.append((segment[position:], position, len(segment)))
    return parts


def _governed_by_the_registrant(text):
    return bool(_MENTION["registrant_subject"].search(text)
                and not _MENTION["preposition"].search(text))


def _list_item(text):
    """An item a list can hold: words, but no clause and not the registrant acting."""
    text = text.strip()
    return bool(text and not _MENTION["clause_word"].search(text)
                and not _MENTION["clause_starter"].search(text)
                and not _MENTION["first_person_subject"].search(text)
                and not _governed_by_the_registrant(text))


def _structure(text, start, end):
    """Why version 1's evidence for one occurrence stands or falls (see the module docstring)."""
    offset, segment = _segment(text, start, end)
    parts = _items(segment)
    begin, finish = start - offset, end - offset
    k = next(index for index in range(0, len(parts), 2)
             if parts[index][1] <= begin and finish <= parts[index][2])
    head, tail = segment[parts[k][1]:begin], segment[finish:parts[k][2]]
    if (_MENTION["clause_word"].search(tail) or _MENTION["clause_starter"].search(tail)
            or _MENTION["party_preposition"].search(tail)):
        return "KEYWORD_PHRASE_IS_A_CLAUSE_OR_NAMES_A_PARTY"
    if _MENTION["registrant_reference"].search(tail):
        return "KEYWORD_PHRASE_NAMES_THE_REGISTRANT_S_OWN_MATTER"
    if _parenthetical_example(text, start):
        return "PARENTHETICAL_EXAMPLE"
    if _MENTION["example_before"].search(text[max(0, start - 40):start]):
        return "EXAMPLE"
    if k == 0:
        return "GOVERNED_BY_ITS_SENTENCE"
    if (_MENTION["clause_word"].search(head) or _MENTION["clause_starter"].search(head)
            or _MENTION["first_person_subject"].search(head)):
        return "KEYWORD_PHRASE_IS_A_CLAUSE"
    if _governed_by_the_registrant(head):
        return "GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"
    coordinated, index, governing = False, k, None
    while index >= 2:
        coordinates = parts[index - 1][1]
        if not _list_item(parts[index - 2][0]):
            governing = parts[index - 2][0]
            # "formal administrative and legal proceedings": a coordinator right
            # before the keyword's phrase joins it to the governing item's last
            # words; it counts only when the phrase is the keyword alone.
            if coordinates and index == k and not re.search(r"\w", tail):
                coordinated = True
            break
        coordinated = coordinated or coordinates
        index -= 2
    if governing is None:
        governing = parts[index][0]
    if _governed_by_the_registrant(governing):
        return "GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"
    index = k
    while index + 2 < len(parts):
        following = parts[index + 2][0].strip()
        if not _list_item(following):
            if _OPENS_WITH_CLAUSE_WORD.search(following):
                return "SERIES_IS_A_SUBJECT"
            break
        coordinated = coordinated or parts[index + 1][1]
        index += 2
    return "LIST_MEMBER" if coordinated else "NO_COORDINATED_SERIES"


def _plain_item(text):
    """Version 3's list item: version 2's, and not naming the registrant acting anywhere."""
    return _list_item(text) and not _MENTION["registrant_actor"].search(text)


def _last(pattern, text):
    found = None
    for found in pattern.finditer(text):
        pass
    return found


def _governor(parts, index, governing):
    """Where the series' closed-class governor stands in its segment, or None.

    The series' first plain item holds a preposition ("including" and "such as"
    among them) and its last one introduces the first member; or the item the
    walk stopped at ends with a preposition and plain words, the first member.
    A preposition opening the sentence governs a fronted phrase, not the series.
    """
    first, first_start = parts[index][0], parts[index][1]
    found = _last(_MENTION["preposition"], first)
    if found is not None and not (first_start == 0 and not re.search(r"\w", first[:found.start()])):
        return first_start + found.start()
    if governing is not None:
        found = _last(_MENTION["preposition"], governing)
        if found is not None and _plain_item(governing[found.end():]):
            return parts[index - 2][1] + found.start()
    return None


def _registrant_governs(segment, position):
    """The nearest subject or object reference to the registrant before ``position`` is it acting.

    A possessive ("our business") is neither and is passed over; "us" is the
    registrant acted on; a relative or subordinating word between the actor
    and ``position`` puts them in different clauses.
    """
    found = None
    for reference in _MENTION["registrant_reference"].finditer(segment[:max(0, position)]):
        actor = _MENTION["registrant_actor"].match(segment, reference.start())
        if actor or reference.group(0).lower() == "us":
            found = (reference, actor)
    if found is None or not found[1]:
        return False
    return not _CLAUSE_STARTER_WORD.search(segment[found[0].end():position])


def _unproven(text, start, end, why):
    """Why version 3 does not accept version 2's category reading, or None if it does."""
    offset, segment = _segment(text, start, end)
    parts = _items(segment)
    begin, finish = start - offset, end - offset
    if why == "PARENTHETICAL_EXAMPLE":
        before = text[_sentence(text, start, end)[0]:text.rfind("(", 0, start)]
        if _registrant_governs(segment, begin) or _registrant_governs(before, len(before)):
            return "GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"
        return None
    if why == "EXAMPLE":
        window = max(0, start - 40)
        marker = _MENTION["example_before"].search(text[window:start])
        if _registrant_governs(segment, window - offset + marker.start()):
            return "GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"
        return None
    k = next(index for index in range(0, len(parts), 2)
             if parts[index][1] <= begin and finish <= parts[index][2])
    head = segment[parts[k][1]:begin]
    if _MENTION["registrant_actor"].search(head):
        return "GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"
    if not _MENTION["head_determiner"].search(head):
        return "KEYWORD_PHRASE_FOLLOWS_OTHER_WORDS"
    if not _MENTION["registrant_reference"].search(segment[:begin]):
        return None
    index, governing = k, None
    while index >= 2:
        if not _plain_item(parts[index - 2][0]):
            governing = parts[index - 2][0]
            break
        index -= 2
    position = _governor(parts, index, governing)
    if _registrant_governs(segment, begin if position is None else position):
        return "GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"
    if position is None:
        return "REGISTRANT_NAMED_AND_NO_GOVERNOR_PROVEN"
    return None


_CATEGORY = {"PARENTHETICAL_EXAMPLE", "EXAMPLE", "LIST_MEMBER"}


def classify(*, text: str, keyword: re.Pattern) -> dict:
    """How an Item 8 block's keyword occurrences and legal-matter statements read.

    Args:
        text: The block's text.
        keyword: The route's own legal keyword, so this never defines a second one.

    Returns:
        ``occurrences`` (each match with ``category_mention`` and why),
        ``exposure`` (the names of the legal-matter statements found),
        ``prose`` and ``left_out``: true only when the block is prose, every
        occurrence is a category mention and no exposure statement is present.
    """
    occurrences = []
    for match in keyword.finditer(text):
        if not (_parenthetical_example(text, match.start())
                or _list_member(text, match.start(), match.end())):
            why = "NEITHER"
        else:
            why = _structure(text, match.start(), match.end())
            if why in _CATEGORY:
                why = _unproven(text, match.start(), match.end(), why) or why
        occurrences.append({"start": match.start(), "end": match.end(), "text": match.group(0),
                            "category_mention": why in _CATEGORY, "why": why})
    exposure = [name for name, pattern in _EXPOSURE if pattern.search(text)]
    prose = bool(_MENTION["prose"].search(text))
    left_out = bool(occurrences and prose and not exposure
                    and all(item["category_mention"] for item in occurrences))
    return {"occurrences": occurrences, "exposure": exposure, "prose": prose,
            "left_out": left_out, "terms_hash": TERMS_HASH}


def left_out_as_category_mention(*, text: str, keyword: re.Pattern) -> bool:
    """Whether a keyword-admitted Item 8 block leaves D02's set (see ``classify``)."""
    return classify(text=text, keyword=keyword)["left_out"]
