"""Read a Part III amendment's whole explanatory note as paragraphs, not markup blocks.

The approved amendment policy has a class for exactly Paramount Global's FY2024
10-K/A - a Part III addition that files no new financial statements, which
leaves the fiscal event window unchanged - and the approved classifier
(``annual_amendment_scope``) refuses it for two mechanical reasons, neither of
them about what the note says:

* the filer's markup puts "10-K/A", "10-K" and "10-K”)," in blocks of their own,
  so a three-paragraph note is thirteen blocks, over the classifier's bound of
  eight blocks - a bound in code, meant to keep a note short;
* its purpose sentence ends "... required by such Items, rather than incorporate
  such information into Part III by reference to a proxy statement." where the
  approved pattern ends at "such Items." - the continuation says why the Items
  are filed here instead of by reference, not what else is amended.

This module is the repair, in Issue #47's own rule file; the classifier is bound
by bytes to earlier generations and is not changed, and an amendment it does
classify keeps its answer. It runs only where the classifier refuses with the
note-scope reasons, and it proves more than the classifier does, because it
relaxes two things:

1. **Paragraphs.** The note's blocks - located exactly as the classifier
   locates them, from its unique heading to the next Part heading or the
   cautionary note - are joined into paragraphs at sentence ends. The bound of
   eight applies to paragraphs.
2. **The whole note, not a matching sentence in it.** Every paragraph must be
   one of four kinds - the purpose, the approved no-change statement, a
   defined-terms sentence naming this registrant, or the approved
   certifications sentence - and the purpose and the no-change statement must
   each occur exactly once. A paragraph of any other kind (a restatement, an
   added exhibit, anything) refuses the note by name.
3. **The purpose.** The approved purpose pattern, or the same pattern whose
   sentence continues with the one recognized explanation - that the Items are
   filed instead of being incorporated from a proxy statement. Any other
   continuation refuses.
4. **The pointer.** The purpose paragraph must name the report it amends: the
   fiscal year end must be the original's report date and the stated original
   filing date the original's filing date.

The Part III structure the classifier checks follows unchanged: Part III and
Part IV only, Items 10-15, exactly one "No financial statements or supplemental
data are filed with this Amendment." declaration, and native facts only from the
governance taxonomy. The result is the approved class, and so the approved
consequence: the event window is cleared; the statement values are not, and the
record still says their admission needs further review.
"""
import re
from datetime import datetime

from .annual_amendment_scope import POLICY, AmendmentScopeError, _source, _words
from .canonical import content_hash
from .normal_annual_input_v2 import exact_json_value

PART_III_CLASS = "PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS"
NOTE_PARAGRAPH_BOUND = 8
REFUSALS_THIS_READS = frozenset({"AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED",
                                 "AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN"})
_SENTENCE_END = re.compile("[.?!][\"'\u201d\u2019)\\]]*$")
# A sentence boundary: terminal punctuation, optional closing quote or bracket,
# whitespace, then a capital or an opening quote. "No. 1", "U.S. or" and
# "Inc., a" do not split.
_SENTENCE_SPLIT = re.compile("(?<=[.?!])(?<!\\bNo\\.)[\"'\u201d\u2019)\\]]*\\s+(?=[A-Z\u201c\"])")
_FORM = "(?:Initial|Original) Form 10-K"
_DATE = r"[A-Z][a-z]+ \d{1,2}, \d{4}"
# The purpose, ending either where the approved pattern ends or with the one
# continuation recognized here. It is a strict sub-language of the approved
# pattern: its middle is the approved ".+?" narrowed to "of the Initial Form
# 10-K", so "Items 10 ... 14 and Item 8 of ..." is not read as Part III only.
_PURPOSE = re.compile(
    "(?:solely )?to amend Part III, Items 10, 11, 12, 13 and 14 of the " + _FORM
    + " to include the information required by such Items(?P<continuation>\\.|, rather than"
    " incorporat(?:e|ing) (?:such|this|the) information (?:into Part III )?by reference"
    " (?:to|from) (?:a|the|its|our) (?:definitive )?proxy statement\\.)$")
_INTRO = re.compile(
    "(?P<registrant>.{1,200}?) is filing this Amendment No\\. (?P<number>\\d+) on Form 10.K/A"
    " \\(this \u201cAmendment\u201d\\) to its Annual Report on Form 10-K for the (?:fiscal )?year"
    " ended (?P<period>" + _DATE + "), originally filed with the (?:Securities and Exchange"
    " Commission|SEC)(?: \\(the \u201cSEC\u201d\\))? on (?P<filed>" + _DATE + ")"
    " \\(the \u201c" + _FORM + "\u201d\\), ")
_NO_CHANGE = re.compile(
    "(?:Except as (?:explicitly |expressly )?set forth herein, )?this Amendment does not"
    " otherwise change, modify or update the disclosures in, or exhibits to, the " + _FORM
    + "\\.")
_DEFINED_TERMS = re.compile(
    r"References (?:in this (?:document|Amendment) )?to .{1,200}? refer to (?P<name>.+?)"
    r" and its consolidated subsidiaries, unless the context otherwise requires\.")


class AmendmentNoteError(AmendmentScopeError):
    """The note could not be read as the approved Part III class; never a disclosure fact."""


def _need(condition, reason):
    if not condition:
        raise AmendmentNoteError(reason)


def _date(text):
    return datetime.strptime(text, "%B %d, %Y").date().isoformat()


def note_paragraphs(document):
    """The explanatory note, located as the classifier locates it, joined at sentence ends."""
    blocks = document["blocks"]
    headings = [index for index, block in enumerate(blocks) if not block["linked"]
                and re.fullmatch(POLICY["explanatory_heading_pattern"], block["text"], re.I)]
    _need(len(headings) == 1, "AMENDMENT_EXPLANATORY_NOTE_NOT_UNIQUE")
    start = headings[0]
    end = next((index for index in range(start + 1, len(blocks))
                if re.fullmatch(POLICY["part_heading_pattern"], blocks[index]["text"], re.I)
                or blocks[index]["text"].upper().startswith("CAUTIONARY NOTE")), len(blocks))
    paragraphs, current = [], []
    for index in range(start + 1, end):
        current.append(index)
        if _SENTENCE_END.search(blocks[index]["text"]):
            paragraphs.append({"block_indices": current,
                               "text": " ".join(blocks[i]["text"] for i in current)})
            current = []
    _need(not current, "AMENDMENT_NOTE_ENDS_INSIDE_A_SENTENCE")
    _need(1 <= len(paragraphs) <= NOTE_PARAGRAPH_BOUND,
          "AMENDMENT_NOTE_PARAGRAPHS_OUT_OF_BOUND:" + str(len(paragraphs)))
    return {"start": start, "end": end, "block_count": end - start - 1,
            "paragraphs": paragraphs}


def sentences(text):
    """The note's sentences; every one of them has to be read, not just one that matches."""
    return [part for part in _SENTENCE_SPLIT.split(text) if part]


def _kind(sentence, *, names, period_end, original_filed):
    """PURPOSE, NO_CHANGE, DEFINED_TERMS or CERTIFICATIONS for an approved sentence; else None."""
    purpose = _PURPOSE.search(sentence)
    if purpose is not None:
        intro = _INTRO.fullmatch(sentence[:purpose.start()])
        if intro is None:
            return None, "AMENDMENT_NOTE_PURPOSE_INTRODUCTION_NOT_RECOGNIZED"
        if not any(_words(intro["registrant"]).startswith(_words(name)) for name in names):
            return None, "AMENDMENT_NOTE_NAMES_ANOTHER_REGISTRANT"
        if (_date(intro["period"]), _date(intro["filed"])) != (period_end, original_filed):
            return None, ("AMENDMENT_NOTE_NAMES_ANOTHER_REPORT:" + _date(intro["period"]) + ":"
                          + _date(intro["filed"]))
        if not re.search(POLICY["part_iii_purpose_pattern"][:-len("\\.")], purpose.group(0), re.I):
            return None, "AMENDMENT_NOTE_PURPOSE_OUTSIDE_THE_APPROVED_PATTERN"
        return "PURPOSE", purpose["continuation"]
    if _NO_CHANGE.fullmatch(sentence):
        return "NO_CHANGE", None
    defined = _DEFINED_TERMS.fullmatch(sentence)
    if defined and any(_words(defined["name"]) == _words(name) for name in names):
        return "DEFINED_TERMS", None
    if re.fullmatch(POLICY["certification_note_pattern"], sentence, re.I):
        return "CERTIFICATIONS", None
    return None, "AMENDMENT_NOTE_SENTENCE_NOT_RECOGNIZED"


def read_part_iii_note(*, original, amendment, company_id, cik, refusal):
    """The approved Part III class for a note the classifier refused on its markup, or a named refusal."""
    _need(refusal in REFUSALS_THIS_READS, "AMENDMENT_NOTE_REFUSAL_NOT_READ_HERE:" + str(refusal))
    _need(original["filing"]["form"] == "10-K" and amendment["filing"]["form"] == "10-K/A",
          "AMENDMENT_SOURCE_FORMS_REQUIRED")
    end = original["filing"]["reportDate"]
    _need(amendment["filing"]["reportDate"] == end
          and amendment["filing"]["filingDate"] >= original["filing"]["filingDate"],
          "AMENDMENT_SAME_FILING_PERIOD_REQUIRED")
    old = _source(**original, company_id=company_id, cik=cik, period_end=end)
    new = _source(**amendment, company_id=company_id, cik=cik, period_end=end)
    note = note_paragraphs(new["document"])
    _need(not set(range(note["start"], note["end"])) & set(new["quoted_block_indices"]),
          "AMENDMENT_NOTE_IS_QUOTED")
    names = new["document"]["registrant_names"]
    read = []
    for number, paragraph in enumerate(note["paragraphs"]):
        for sentence in sentences(paragraph["text"]):
            kind, detail = _kind(sentence, names=names, period_end=end,
                                 original_filed=original["filing"]["filingDate"])
            if kind is None:
                raise AmendmentNoteError(detail + ":" + str(number))
            read.append({"paragraph": number, "kind": kind, "detail": detail,
                         "sentence": sentence})
    kinds = [row["kind"] for row in read]
    _need(kinds.count("PURPOSE") == 1 and kinds.count("NO_CHANGE") == 1,
          "AMENDMENT_NOTE_PURPOSE_AND_NO_CHANGE_NOT_EACH_ONCE")
    blocks = new["document"]["blocks"]
    parts = {block["text"].upper() for block in blocks if not block["linked"]
             and re.fullmatch(POLICY["part_heading_pattern"], block["text"], re.I)}
    items = {re.match(POLICY["item_heading_pattern"], block["text"], re.I).group(1)
             for block in blocks if not block["linked"]
             and re.match(POLICY["item_heading_pattern"], block["text"], re.I)}
    statements = [block for block in blocks
                  if re.search(POLICY["no_financial_statement_pattern"], block["text"], re.I)]
    governance = all(re.fullmatch(r"https?://xbrl\.sec\.gov/ecd/[0-9]{4}", fact["concept"][0])
                     for fact in new["non_dei_native_facts"])
    _need(parts == {"PART III", "PART IV"} and items == {"10", "11", "12", "13", "14", "15"}
          and len(statements) == 1 and governance, "PART_III_ONLY_SOURCE_SCOPE_NOT_PROVEN")
    period_equal = old["period"] == new["period"]
    _need(period_equal, "AMENDMENT_FISCAL_WINDOW_CHANGED")
    body = {"record_type": "HISTORICAL_AMENDMENT_NOTE_SCOPE", "schema_version": 1,
            "company_id": company_id, "classification": PART_III_CLASS,
            "read_because_the_classifier_refused": refusal,
            "amendment": {"filing": amendment["filing"], "raw_sha256": new["raw_sha256"],
                          "source_reference_id": new["source_reference"]["source_reference_id"]},
            "original": {"filing": original["filing"], "raw_sha256": old["raw_sha256"]},
            "note": {"block_count": note["block_count"],
                     "paragraphs": [{"block_indices": paragraph["block_indices"],
                                     "text": paragraph["text"]}
                                    for paragraph in note["paragraphs"]],
                     "sentences": read,
                     "purpose_continuation": next(row["detail"] for row in read
                                                  if row["kind"] == "PURPOSE")},
            "pointer": {"period_end": end, "original_filing_date": original["filing"]["filingDate"]},
            "details": {"parts": sorted(parts), "items": sorted(items),
                        "no_new_financial_statement_declarations": [b["text"] for b in statements],
                        "non_dei_facts_are_governance_taxonomy": governance,
                        "non_dei_native_facts": len(new["non_dei_native_facts"])},
            "issues": [], "fiscal_window_unchanged": True,
            "unchanged_input_classes": [POLICY["event_input_class"]],
            "original_statement_admission_requires_further_review": True,
            "not_covered_metric_ids": POLICY["not_covered_metric_ids"],
            "policy_hash": content_hash(value=POLICY), "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "scope_id": content_hash(value=body)}
