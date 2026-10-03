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

What it decides from and what it does not. A list member is read from the
characters beside the word, not from what the list is about; the paragraph's
legal-matter vocabulary is read anywhere in the block, so a paragraph that says
"pending" or "accrued" about something else stays in (the cautious direction:
it can keep a paragraph a reader would leave out, and cannot drop one a reader
would keep for the reasons it reads). A block that is not prose - no sentence
punctuation, such as a heading "Litigation and Regulatory Matters" - is never
removed: a label names what follows rather than listing a category. A
self-insurance paragraph shows why the two properties must hold together: its
keyword is a list member ("losses, settlements, litigation costs and other
factors") and it is a disclosure, because the registrant accrues for its own
claims. The vocabulary lives in ``catalog/r6/D02_item8_category_28_v1.json``.
"""
from __future__ import annotations

import re
from pathlib import Path

from .canonical import content_hash, strict_json_file

RECORD_TYPE = "D02_ITEM_8_CATEGORY_MENTION_TERMS"
_TERMS_PATH = Path(__file__).resolve().parents[2] / "catalog/r6/D02_item8_category_28_v1.json"


class CategoryMentionTermsError(ValueError):
    """The vocabulary file is not the one this module reads."""


def _load(path):
    terms = strict_json_file(path=path)
    if (type(terms) is not dict or terms.get("record_type") != RECORD_TYPE
            or terms.get("schema_version") != 1 or terms.get("metric_id") != "D02"
            or type(terms.get("category_mention")) is not dict
            or set(terms["category_mention"]) != {"separator_before", "separator_after",
                                                  "parenthetical_example", "prose"}
            or type(terms.get("exposure")) is not list or not terms["exposure"]
            or any(type(item) is not dict or set(item) != {"name", "pattern", "why"}
                   for item in terms["exposure"])
            or len({item["name"] for item in terms["exposure"]}) != len(terms["exposure"])):
        raise CategoryMentionTermsError("D02_CATEGORY_MENTION_TERMS_INVALID:" + str(path))
    return terms


_TERMS = _load(_TERMS_PATH)
TERMS_HASH = content_hash(value=_TERMS)
_MENTION = {name: re.compile(pattern, re.I)
            for name, pattern in _TERMS["category_mention"].items()}
_EXPOSURE = tuple((item["name"], re.compile(item["pattern"], re.I))
                  for item in _TERMS["exposure"])


def _parenthetical_example(text, start):
    """The occurrence sits in an open parenthetical that begins "(including" or "(such as"."""
    opened = text.rfind("(", 0, start)
    if opened < 0 or text.rfind(")", 0, start) > opened:
        return False
    return bool(_MENTION["parenthetical_example"].search(text[opened:start]))


def _list_member(text, start, end):
    """A list separator stands right before or right after the occurrence."""
    return bool(_MENTION["separator_before"].search(text[max(0, start - 40):start])
                or _MENTION["separator_after"].search(text[end:end + 12]))


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
        parenthetical = _parenthetical_example(text, match.start())
        listed = _list_member(text, match.start(), match.end())
        occurrences.append({"start": match.start(), "end": match.end(), "text": match.group(0),
                            "category_mention": parenthetical or listed,
                            "why": ("PARENTHETICAL_EXAMPLE" if parenthetical
                                    else "LIST_MEMBER" if listed else "NEITHER")})
    exposure = [name for name, pattern in _EXPOSURE if pattern.search(text)]
    prose = bool(_MENTION["prose"].search(text))
    left_out = bool(occurrences and prose and not exposure
                    and all(item["category_mention"] for item in occurrences))
    return {"occurrences": occurrences, "exposure": exposure, "prose": prose,
            "left_out": left_out, "terms_hash": TERMS_HASH}


def left_out_as_category_mention(*, text: str, keyword: re.Pattern) -> bool:
    """Whether a keyword-admitted Item 8 block leaves D02's set (see ``classify``)."""
    return classify(text=text, keyword=keyword)["left_out"]
