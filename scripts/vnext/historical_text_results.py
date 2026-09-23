"""Close a numbered Form 10-K item at the form's unnumbered Part I item.

``text_coverage`` ends a numbered item at the next numbered heading, and
``_SUCCESSOR`` deliberately allows a later number so that a registrant omitting
an inapplicable item still has a boundary. Form 10-K also lets a registrant
carry the executive officer information as an unnumbered item inside Part I.
When both apply the numbered item runs past that unnumbered one, and the officer
section is reported as the numbered item's own disclosure.

Measured on the ten companies' own filings: eight close Item 3 at ``Item 4. Mine
Safety Disclosures``; Pfizer files no Item 4, so its Item 3 closes at Item 5 and
absorbs the officer section between them. Five of the nine carry the unnumbered
item at all, and Marriott's and Southwest's sit two and four blocks past a
boundary that happens to hold. It is a form element meeting a deliberate
widening, not one registrant's layout.

The repair belongs in ``text_coverage.build_text_document``. It cannot go there:
that file's bytes are named by ``issue_28_v11``'s rule set, which
``issue_47_v1`` loads through its parent chain and re-checks on both roots, so
changing it stops every Requirement from v11 onward from loading. This successor
therefore narrows the located ranges for the historical route only, and the
ordinary route keeps the defect until a generation that can re-record that file
carries the same rule.

A second correction shares the file. ``legal_risk_candidates`` gives a located
referenced note its own range only when no other range already contains it, as
a deduplication guard, and the side effect is that a note inside Item 8 loses
its note identity and is filtered by Item 8's keyword rule. Ford's note falls
outside Item 8 and is taken whole; the other five referenced notes are inside
it and drop blocks that name a proceeding in the filing's own words - 39 blocks
and 19,918 characters for Pfizer alone. ``referenced_note_candidates`` keeps
the note as a note and deduplicates by the rule that decides it honestly: the
innermost range containing a block owns it.

``_derive_candidate``, ``build_text_review_unit``, ``_note_references``,
``_excerpt``, ``_substantive`` and the record shape validator are the frozen
ones, called unchanged. ``build_text_evidence``, ``reviewed_text_observations``
and ``replay_text_result`` are duplicated for one reason each: they look up
``prepare_business_text_sources`` and each other as module globals, so a
successor cannot reach them without rebinding names in a frozen module. The
duplication is held to the original by
``tests/vnext/test_historical_text_boundary.py``, which requires this module's
candidate, Evidence, review unit and Result to equal the frozen module's exactly
on every filing where neither correction changes anything.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
import copy
import re

from .canonical import content_hash, sha256_bytes
from .records import validate_record
from .text_business_candidates import (_ACTION, _AUTHORITY, _LEGAL, _NEGATION, _POLICY_HASH,
                                       _PROSPECTIVE, _check_document, _excerpt, _note_references,
                                       _ranges, _substantive)
from . import text_results_v2 as frozen
from .text_results_v2 import TextResultV2Error, build_text_review_unit

SECTION_BOUNDARY_POLICY = "FORM_UNNUMBERED_PART_I_ITEM_V1"
SUPPORTED_METRICS = ("D02",)

# Form 10-K General Instruction G(3) names the item but leaves the registrant an
# "appropriate caption", so the accepted captions are the observed wordings and
# this is the module's stated limitation rather than a closed rule. The whole
# block must be the caption: an emphasized subheading inside an item's own body
# does not end it, and neither does a signature line. Both exist in this
# repository's own filings - Macy's block 774 and Paramount's block 1348 name a
# chief executive officer inside Item 8 - and both are excluded by the anchors.
_FORM_UNNUMBERED_ITEM = re.compile(
    r"(?:information about (?:our|the) executive officers(?: of the registrant)?"
    r"|executive officers of the (?:registrant|company))", re.I)


def _need(condition, reason):
    if not condition:
        raise TextResultV2Error(reason)


def form_unnumbered_item_blocks(*, document):
    """Block indices whose whole text is the form's unnumbered Part I caption.

    Linked blocks are contents entries pointing at the section, not the section.
    """
    return [index for index, block in enumerate(document["blocks"])
            if not block["linked"] and _FORM_UNNUMBERED_ITEM.fullmatch(block["text"].strip())]


def narrow_document_sections(*, document):
    """Re-derive the located ranges with the unnumbered item as a closing boundary.

    The blocks, the bytes and every other field are the frozen derivation's.
    Only ``sections`` changes, and the document records both the policy that
    changed it and the identity of the derivation it came from, so a reader can
    tell the two apart instead of finding two ids for the same bytes.
    """
    boundaries = form_unnumbered_item_blocks(document=document)
    sections, narrowed = {}, []
    for section_id, section in document["sections"].items():
        candidates = []
        for candidate in section["candidates"]:
            inside = [index for index in boundaries
                      if candidate["start_block"] <= index < candidate["end_block_exclusive"]]
            if not inside:
                candidates.append(candidate)
                continue
            end = min(inside)
            narrowed.append({"section_id": section_id, "start_block": candidate["start_block"],
                             "original_end_block_exclusive": candidate["end_block_exclusive"],
                             "end_block_exclusive": end, "boundary_block_index": end,
                             "boundary_text": document["blocks"][end]["text"],
                             "dropped": end <= candidate["start_block"]})
            # A range whose first block is already the other item's holds none of
            # this item's text. Reporting it as empty would be an invented
            # boundary; dropping the candidate lets the status say MISSING.
            if end <= candidate["start_block"]:
                continue
            candidates.append({**candidate, "end_block_exclusive": end,
                               "closing_heading": {"item": None, "block_index": end,
                                                   "heading_end_index": end,
                                                   "form_unnumbered_part_i_item": True}})
        sections[section_id] = {
            "status": ("LOCATED" if len(candidates) == 1 else "AMBIGUOUS" if candidates else "MISSING"),
            "candidates": candidates}
    if not narrowed:
        return document
    corrected = {key: value for key, value in document.items() if key != "text_document_id"}
    corrected["sections"] = sections
    corrected["section_boundary_policy"] = SECTION_BOUNDARY_POLICY
    corrected["narrowed_sections"] = narrowed
    corrected["frozen_text_document_id"] = document["text_document_id"]
    corrected["text_document_id"] = content_hash(value=corrected)
    return corrected


_QUOTED_CAPTION = re.compile(r"[\"\u201c\u2018']([^\"\u201c\u201d\u2018\u2019']{4,120})[\"\u201d\u2019']")


def _normalized(text):
    return " ".join(text.split()).strip(" .:;,\u2014-").casefold()


_SPAN = re.compile(rb"<span([^<>]*)>\s*$")
_STYLE_ATTR = re.compile(rb'style="([^"]*)"')


def caption_style(*, raw_bytes, block):
    """The declaration the filing gives this caption's own span.

    The level a caption sits at is not in the parsed flags - Lumen marks a
    topic caption and a case caption both emphasized, Marriott marks neither -
    but each filing carries it in its own bytes, and differently: Lumen and
    Paramount separate a topic from a case by italic, Marriott by an underline
    and a 22.5pt indent. Comparing a caption against its own document is
    therefore the signal; no convention is assumed across filers. Colour is
    dropped because it varies within a level.
    """
    window = raw_bytes[max(block["raw_start_byte"] - 300, 0):block["raw_start_byte"]]
    span = _SPAN.search(window)
    if span is None:
        return None
    style = _STYLE_ATTR.search(span.group(1))
    if style is None:
        return None
    parts = sorted(part.strip() for part
                   in style.group(1).decode("utf-8", "replace").split(";") if part.strip())
    return "; ".join(part for part in parts if not part.startswith("color"))


def _caption_like(document, block):
    """A short standalone heading, judged on the block's own text.

    The parsed flags give no level: Lumen marks a topic caption and a case
    caption both emphasized, and Marriott marks neither. What every caption in
    this corpus does share is being substantive, short and unpunctuated, and a
    sentence that happens to look like one truncates the section early - an
    under-capture that is visible - rather than admitting a neighbouring one.
    """
    text = block["text"].strip()
    return (_substantive(document, block) and len(text) <= 120
            and not text.endswith((".", ":", ";", ",", "\u3002")))


_LETTERED_SUB_NOTE = re.compile(r"^(\d{1,2})([A-H])$")
_TOP_LEVEL_LETTER = re.compile(r"^([A-H])[.)\s\u2014-]\s*(\S.{2,88})$")


def _top_level_letter(document, block):
    """The letter of a sub-note heading, when the block is one.

    A sub-note heading is short, standalone and starts with its own letter.
    ``A1. Legal Proceedings--Patent Litigation`` is nested under A and does not
    match, because the letter is followed by a digit rather than a separator.
    """
    text = block["text"].strip()
    if block["linked"] or len(text) > 90:
        return None
    match = _TOP_LEVEL_LETTER.match(text)
    return None if match is None else match.group(1)


def _note_heading(document, section, block):
    """A short emphasized heading inside a note the filing itself pointed at.

    The inherited `_substantive` needs twelve characters, which is right for
    open-ended scanning: it is what keeps page numbers, tick marks and stray
    fragments out. Inside a note an Item incorporated by reference it is wrong,
    because the headings there are product and matter names and those are
    short. Reading Pfizer's Note 16A against the filing found Zantac (six
    characters), Chantix (seven), Paxlovid and Asbestos (eight) and Docetaxel
    (nine) dropped, while Orgovyx (relugolix), Eliquis (apixaban), Oxbryta
    (voxelotor), Nurtec (rimegepant) and Xtandi (enzalutamide) were kept -
    whether a product heading survived depended on how long its generic name
    was, which is not a rule anyone would write down. The paragraphs beneath
    them were all present, so what the bound removed was the label saying which
    matter each paragraph is about.

    This widens nothing else. It applies only inside a located note scope,
    only to an emphasized unlinked block, and only to one that carries a
    letter - so the bare page numbers in the same run stay out, and the
    running-header blocks are already gone as furniture.
    """
    if not section.startswith("NOTE_"):
        return False
    text = block["text"].strip()
    # The registrant's own name is eleven characters for this filer and is
    # excluded by _substantive for exactly that reason, so it is excluded here
    # too rather than let back in through the side the bound was guarding.
    names = {re.sub(r"\W", "", name).casefold()
             for name in document.get("registrant_names", [])}
    return bool(text and block.get("emphasized") and not block.get("linked")
                and re.search(r"[A-Za-z]", text) and len(text) < 12
                and re.sub(r"\W", "", text).casefold() not in names)


def _d02_section(section, text):
    """Whether a declared range puts a block in D02's excerpt set.

    Item 3 and a note an Item incorporates are the approved source itself, so
    every substantive block in them counts; Item 8 at large is not, so a block
    there needs the legal keyword. Both the ordinary path and the hyperlinked
    one below ask this, because restating it in two places is how they drift.
    """
    return bool(section == "ITEM_3" or section.startswith("NOTE_")
                or section == "ITEM_8" and _LEGAL.search(text))


def _hyperlinked_sentence(*, document, block):
    """A sentence the inherited rule drops for being a short hyperlink.

    `_substantive` rejects any linked block under 120 characters. That clause
    is load-bearing - across the six filings read here it holds 365 blocks
    inside the declared ranges - and it is wrong about Pfizer's Item 3, which
    is one 77-character hyperlinked sentence, "Certain legal proceedings in
    which we are involved are discussed in Note 16A.", and so is the whole of
    the item the approved source names first, dropped entire. Lumen is the
    control: its Item 3 is the same kind of sentence, an incorporation by
    reference to a note, 226 characters and not hyperlinked, and it is taken.
    The two filings answer the same content differently, and the difference is
    whether the registrant wrapped the sentence in an anchor.

    Nothing new decides which is which. Of the 365 held blocks only 14 could
    reach D02 at all; thirteen are the string "Table of Contents", and the
    frozen rule's own navigation-header pattern already rejects every one of
    them once the link flag is out of the way. So this asks `_substantive` the
    question with the hyperlink taken off rather than inventing a second
    discriminator, and the corpus answers 13 out of 14 correctly by itself.

    There is no length test because there is nothing for one to do: this is
    only asked after `_substantive` has already refused the block, and the
    only way it refuses a linked block of 120 characters or more is on one of
    the conditions re-asked here.

    What this leaves open is recorded rather than guarded: a hyperlink of
    twelve characters or more that is not a navigation header and repeats
    inside a note would be admitted once per occurrence. No filing here holds
    one, so a condition against it would be an unexercised guard, and this
    Issue has enough of those already.
    """
    if not block["linked"]:
        return False
    return bool(_substantive(document, {**block, "linked": False}))


def _page_furniture(*, blocks, start, stop, repeated):
    """Blocks that repeat *and* sit next to another repeating block.

    Repetition alone was the rule, and it is right about what it was written
    for: a running header repeats verbatim on every page of a section, so
    Pfizer's five-block group - registrant name, form title, page number,
    "Notes to Consolidated Financial Statements", "Pfizer Inc. and Subsidiary
    Companies" - is correctly dropped five times over.

    It is wrong about a heading that legitimately repeats. Reading Pfizer's
    Note 16A against the filing found "Comirnaty (tozinameran)" dropped twice,
    once under "Actions in Which We are the Defendant" and once under "Matters
    Involving Pfizer and its Collaboration/Licensing Partners", because a
    product can be the subject of two different matters in one note.

    What separates them is that furniture travels in company: a running header
    is a run of blocks that repeats together, and each of its members has a
    repeating neighbour. A repeated heading stands between two blocks that
    occur once. So a repeated block is furniture when the block before or after
    it also repeats, which needs no threshold and no list of known captions.
    """
    repeats = {index for index in range(start, stop)
               if repeated[_normalized(blocks[index]["text"])] > 1}
    return [index for index in sorted(repeats)
            if (index - 1 in repeats) or (index + 1 in repeats)]


def _lettered_sub_note_scopes(*, document, note, blocks, start, stop, repeated):
    """The sub-note a reference named, when only its parent could be numbered.

    The scope runs from the named letter's heading to the next sub-note letter,
    so a reference to 16A takes Legal Proceedings and not the guarantees,
    commitments, contingent consideration and insurance that follow it. A
    reference whose letter has no heading returns nothing: the gap stays
    visible in the coverage record rather than being filled with the parent.
    """
    match = _LETTERED_SUB_NOTE.match(str(note.get("requested_reference", "")).upper())
    if match is None:
        return []
    headings = [(index, _top_level_letter(document, blocks[index]))
                for index in range(start, stop)]
    headings = [(index, letter) for index, letter in headings if letter is not None
                and repeated[_normalized(blocks[index]["text"])] == 1]
    named = [index for index, letter in headings if letter == match.group(2)]
    if len(named) != 1:
        return []
    begin = named[0]
    following = [index for index, _ in headings if index > begin]
    end = following[0] if following else stop
    if begin >= end:
        return []
    furniture = _page_furniture(blocks=blocks, start=begin, stop=end, repeated=repeated)
    return [{"section_id": note["section_id"] + "_SUB_" + match.group(2),
             "start_block": begin, "end_block_exclusive": end,
             "requested_reference": note["requested_reference"],
             "scope_relation": "LOCATED_LETTERED_SUB_NOTE",
             "caption_text": blocks[begin]["text"],
             "repeated_furniture_blocks": furniture}]


def incorporated_scopes(*, document, raw_bytes, reference, note):
    """The parts of a referenced note that Item 3 says it incorporates.

    The filings name their own limits, and four shapes appear in this corpus:

    * a caption inside the note - Marriott's "Litigation, Claims, and
      Government Investigations" in Note 7, Paramount's "Legal Matters" in
      Note 18;
    * two captions - Lumen's "Principal Proceedings" and "Other Proceedings,
      Disputes and Contingencies" in Note 17, whose remaining sections are
      contractual commitments, right-of-way and purchase commitments;
    * the note's own title quoted - Salesforce's Note 14 "Legal Proceedings
      and Claims", which is a name for the whole note, not a limit inside it;
    * no caption at all - Ford's "See Note 24".

    A named caption runs to the next named caption, and the last one runs to
    the next caption-like block. Taking the container instead was measured and
    is wrong in both directions this corpus shows: it admits Marriott's
    guarantee table, letters of credit and insurance recoveries, which its own
    Item 3 does not incorporate, and fifteen blocks of Lumen's contractual
    commitments.
    """
    blocks = document["blocks"]
    start, stop = note["start_block"], note["end_block_exclusive"]
    repeated = Counter(_normalized(blocks[index]["text"]) for index in range(start, stop))
    if note.get("scope_relation") != "EXACT_NOTE":
        # The reference named a lettered sub-note and `_note_references` found
        # only its parent, which it records as WIDER_PARENT_NOTE. Taking the
        # parent whole would be over-capture by the resolver's own
        # classification; locating the sub-note is what the reference asked
        # for. Pfizer's Item 3 names Note 16A, and Note 16 carries
        # "A. Legal Proceedings" at block 3821 with B, C, D and E - guarantees,
        # commitments, contingent consideration and insurance - after it.
        return _lettered_sub_note_scopes(document=document, note=note, blocks=blocks,
                                         start=start, stop=stop, repeated=repeated)
    quoted = []
    for occurrence in reference["source_occurrences"]:
        quoted.extend(_normalized(m.group(1)) for m in _QUOTED_CAPTION.finditer(occurrence["text"]))
    heading = _normalized(blocks[start - 1]["text"]) if start else ""
    named = sorted({index for index in range(start, stop)
                    if _normalized(blocks[index]["text"]) in quoted
                    and _caption_like(document, blocks[index])})
    # A quoted note title names the whole note; a quoted caption limits it.
    inside = [index for index in named if _normalized(blocks[index]["text"]) != heading]
    if not inside:
        return [note]
    scopes = []
    for position, begin in enumerate(inside):
        if position + 1 < len(inside):
            end = inside[position + 1]
        else:
            # A page break repeats the registrant name and the "(Continued)"
            # line in the same style as a topic caption, four times inside
            # Paramount's Note 18 alone, so a style match on its own ends the
            # section at the first page break. Running furniture repeats; a
            # section caption does not.
            style = caption_style(raw_bytes=raw_bytes, block=blocks[begin])
            siblings = [index for index in range(begin + 1, stop)
                        if _caption_like(document, blocks[index])
                        and repeated[_normalized(blocks[index]["text"])] == 1
                        and (caption_style(raw_bytes=raw_bytes, block=blocks[index]) == style
                             if style is not None else True)]
            end = siblings[0] if siblings else stop
        if begin >= end:
            continue
        # The same repetition that identifies a page break as furniture rather
        # than a caption also keeps it out of the excerpts. This applies to the
        # scopes this successor creates; a wholesale note keeps the inherited
        # behaviour, which already carries Ford's running headers.
        furniture = _page_furniture(blocks=blocks, start=begin, stop=end, repeated=repeated)
        scopes.append({"section_id": note["section_id"] + "_CAPTION_" + str(begin),
                       "start_block": begin, "end_block_exclusive": end,
                       "requested_reference": note["requested_reference"],
                       "scope_relation": "INCORPORATED_CAPTION",
                       "caption_text": blocks[begin]["text"],
                       "repeated_furniture_blocks": furniture})
    return scopes


# An audit report's own title, as its own block. Measured on six filings: every
# real heading carries leading emphasis and every mention of the report that is
# not a heading does not - Marriott's two table-of-contents lines, Southwest's
# reference, Enphase's "(PCAOB ID No. 34)" line and Ford's whole Item 8, which is
# one cross-reference block.
_AUDIT_REPORT_TITLE = re.compile(
    r"\Areport of independent registered public accounting firm\Z", re.I)
# Where it ends. Five of the six close with the firm's signature block; Pfizer's
# has no /s/ block at all and closes with the auditor-tenure sentence, whose
# wording is not fixed either - it says it cannot determine the year it began.
# A rule built on the signature alone passes five filings and fails the one that
# motivated it, which is why six were read before this was written.
_AUDIT_REPORT_SIGNATURE = re.compile(r"\A/s/\s*\S")
_AUDIT_REPORT_TENURE = re.compile(r"serv(?:ed|ing)\s+as\s+.{0,60}?auditor", re.I)
_AUDIT_REPORT_CLOSER_MAX_CHARS = 400


def audit_report_spans(*, document, ranges=None):
    """The block ranges an independent auditor's report occupies.

    D02's approved source names three places - Item 3, the legal proceedings
    section and the contingencies notes. The audit report is none of them, and
    it is inside Item 8, which the scan uses as a stand-in for the third. So a
    critical audit matter about litigation matches the legal wording and is
    taken as if the registrant had disclosed it.

    The argument for excluding it is document part supported by content, not
    speaker. entity_scope registrant says which entity the disclosure concerns,
    and a critical audit matter about the registrant's litigation concerns the
    registrant; what it discloses is the audit, and the procedures paragraph is
    a description of what the auditor did.

    Measured across six filings, this excludes four blocks in one of them and
    nothing in the other five - Pfizer's auditor names a litigation critical
    audit matter and the others' do not. So the defect is not routine, and it
    is structural: any filing whose auditor names one is exposed to it.

    An opening with no closer excludes nothing and is reported instead. An
    unbounded exclusion could drop real disclosures silently, and a known
    over-take that is registered is the lesser of the two.

    ``ranges`` restricts which openings count, and the caller passes the ranges
    it is about to scan. Pfizer carries a third report - the internal control
    one, in Item 9A - which has no signature and no tenure sentence either, so
    it never closes. It is also outside every scanned range, so it can exclude
    nothing; reporting it as unclosed would invite a reader to think something
    was missed when nothing was at stake. The closer is still looked for across
    the whole document, because a report can end just past the range it opens
    in.
    """
    blocks = document["blocks"]
    inside = None if ranges is None else {
        index for scope in ranges
        for index in range(scope["start_block"], scope["end_block_exclusive"])}
    spans, unclosed = [], []
    for opening, block in enumerate(blocks):
        if inside is not None and opening not in inside:
            continue
        if not (block.get("leading_emphasis")
                and _AUDIT_REPORT_TITLE.match(block["text"].strip())):
            continue
        closing = next((index for index in range(opening + 1, len(blocks))
                        if len(blocks[index]["text"]) <= _AUDIT_REPORT_CLOSER_MAX_CHARS
                        and (_AUDIT_REPORT_SIGNATURE.match(blocks[index]["text"].strip())
                             or _AUDIT_REPORT_TENURE.search(blocks[index]["text"]))), None)
        if closing is None:
            unclosed.append(opening)
            continue
        spans.append({"start_block": opening, "end_block_exclusive": closing + 1,
                      "closed_by": ("SIGNATURE"
                                    if _AUDIT_REPORT_SIGNATURE.match(
                                        blocks[closing]["text"].strip())
                                    else "AUDITOR_TENURE_STATEMENT")})
    return {"spans": spans, "unclosed_openings": unclosed}


def referenced_note_candidates(*, document, raw_bytes):
    """`legal_risk_candidates` with a referenced note kept as a note.

    The frozen scan appends a located note range only when no other range
    already contains it. That is a deduplication guard: without it a note
    inside Item 8 would be scanned twice and the excerpt set would hold the
    same block under two section ids. The side effect is semantic. A note
    outside Item 8 keeps its `NOTE_` id and is taken whole; a note inside it
    silently becomes Item 8 text and is kept only where `_LEGAL` matches
    litigation, lawsuit, legal proceeding, legal claim, loss contingency or
    litigation reserve.

    Measured on the nine filings: Ford's Note 24 falls outside Item 8 and all
    33 of its substantive blocks reach the result. Every other referenced note
    is inside Item 8, and blocks naming a proceeding in the filing's own words
    are dropped - 39 blocks and 19,918 characters for Pfizer, which is more
    than its whole result contains, 11 and 7,689 for Lumen, 6 and 6,851 for
    Paramount, 4 and 5,097 for Salesforce, 1 and 164 for Marriott. They
    describe putative class actions, civil investigative demands, FCC letters
    of inquiry and complaints filed in named courts.

    `REFERENCED_NOTES` is one of D02's three declared sections, so this
    restores the declared meaning rather than widening it. Deduplication is
    kept by the rule that decides it honestly: the innermost range containing
    a block owns it, so Item 8 does not also scan the note it contains.

    What is not settled here is which part of a note is incorporated. Five of
    the filings name a caption in Item 3 - Lumen names two subheadings inside
    a note also holding commitments and other items - and this takes the whole
    note, as Ford's already did. Capturing exactly the named caption is the
    follow-up recorded in the evidence directory; it reduces to this whenever
    Item 3 names no caption, as Pfizer's does not.
    """
    _check_document(document)
    ranges, reasons = _ranges(document, ["ITEM_1A", "ITEM_3", "ITEM_8"])
    references = _note_references(document, ranges)
    for reference in references:
        if reference["status"] != "LOCATED_NOTE_RANGE":
            reasons.append("UNRESOLVED_" + reference["reference"].upper().replace(" ", "_"))
            continue
        note = reference["range_candidates"][0]
        for scope in incorporated_scopes(document=document, raw_bytes=raw_bytes,
                                         reference=reference, note=note):
            if not any(r["section_id"] == scope["section_id"]
                       and r["start_block"] == scope["start_block"] for r in ranges):
                ranges.append(scope)
    # The furniture criterion was attached only to the scopes this successor
    # builds, so Item 3 and a wholesale note went without it. Reading four
    # excerpt sets against their filings found the consequence: Ford's result
    # carries its running header three times over - registrant name, "Notes to
    # the Financial Statements", "NOTE 24 ... (Continued)" - because its Item 3
    # names no caption and the whole note is taken. A running header is not a
    # disclosure in any scope, so every scope gets the same criterion.
    #
    # Filled in rather than recomputed: a sub-note scope counts repeats over
    # its parent note's range, which is a different question from counting them
    # over the sub-note, and recomputing would silently answer the second one
    # for Pfizer. Measured over all eleven filings that have a D02 excerpt set:
    # eight blocks leave, all of them Ford's running header, and no other
    # filing moves. Enphase's footer is not among them - it carries the page
    # number, so no two instances are the same text and repetition cannot see
    # it. That one stays a registered defect rather than motivating a second
    # criterion invented from a single filing.
    #
    # Held beside the scopes rather than written into them. The first version
    # assigned the list onto each scope, and `checked_ranges` is part of the
    # record: Macy's candidate stopped being byte-identical to the frozen
    # implementation's although not one of its three excerpts moved. A change
    # that moves eight blocks in one filing should change one filing's bytes.
    # The cost is that the record stays silent about what these scopes treated
    # as furniture, where a caption scope says so.
    #
    # Added to D02's branch only, and the reason is the same one already written
    # down for the audit-report rule: the loop below builds D03's regulatory set
    # out of the same blocks, and a `continue` here would take these out of it
    # too. D03 has its own approved source and nothing in this reading measured
    # it. Removing the guard and letting the skip apply to both drops two of
    # Macy's forty-two regulatory candidates, in a filing whose D02 set does not
    # move at all - so the cost of getting this wrong is invisible in the metric
    # being worked on.
    d02_furniture = {}
    for scope in ranges:
        if "repeated_furniture_blocks" in scope:
            continue
        start, stop = scope["start_block"], scope["end_block_exclusive"]
        repeated = Counter(_normalized(document["blocks"][index]["text"])
                           for index in range(start, stop))
        d02_furniture[id(scope)] = set(_page_furniture(
            blocks=document["blocks"], start=start, stop=stop, repeated=repeated))
    owner = {}
    for scope in ranges:
        for index in range(scope["start_block"], scope["end_block_exclusive"]):
            held = owner.get(index)
            if held is None or _width(scope) < _width(held):
                owner[index] = scope
    audit = audit_report_spans(document=document, ranges=ranges)
    audited = {index for span in audit["spans"]
               for index in range(span["start_block"], span["end_block_exclusive"])}
    legal, regulatory, excluded = [], [], []
    for scope in ranges:
        section = scope["section_id"]
        furniture = set(scope.get("repeated_furniture_blocks", ()))
        running_header = d02_furniture.get(id(scope), frozenset())
        for index in range(scope["start_block"], scope["end_block_exclusive"]):
            if owner[index] is not scope or index in furniture:
                continue
            block = document["blocks"][index]
            if not _substantive(document, block) and not _note_heading(document, section, block):
                if section == "ITEM_3" and block["text"].strip().casefold() in {"none", "none."}:
                    legal.append(_excerpt(document, block, section,
                                          ["EXPLICIT_NONE_IN_THIS_SECTION_ONLY"]))
                # Appended to D02's list only, never to the shared gate. Adding
                # an alternative to _substantive up here would widen D03's
                # regulatory set on every filing at the same time, which is the
                # mistake the audit-report rule already made once.
                elif (index not in audited and index not in running_header
                      and _hyperlinked_sentence(document=document, block=block)
                      and _d02_section(section, block["text"])):
                    legal.append(_excerpt(
                        document, block, section,
                        ["EXPLICIT_LEGAL_SECTION_TEXT" if section == "ITEM_3"
                         else "LEGAL_OR_CONTINGENCY_LANGUAGE_IN_NOTES"]))
                continue
            text = block["text"]
            if _d02_section(section, text) and index not in running_header:
                # Only D02's branch. The first version skipped the whole block,
                # which silently took the same blocks out of D03's regulatory
                # set as well - a different metric with its own approved source,
                # on four filings this rule was supposed to leave alone. The
                # identical candidate counts hid it; comparing the records did
                # not.
                if index in audited:
                    excluded.append(index)
                else:
                    legal.append(_excerpt(document, block, section,
                                          ["EXPLICIT_LEGAL_SECTION_TEXT" if section == "ITEM_3"
                                           else "LEGAL_OR_CONTINGENCY_LANGUAGE_IN_NOTES"]))
            if _ACTION.search(text) or _AUTHORITY.search(text):
                labels = ["ACTION_LANGUAGE_PRESENT" if _ACTION.search(text)
                          else "AUTHORITY_OR_GENERAL_REGULATION_MENTION"]
                if _PROSPECTIVE.search(text):
                    labels.append("HYPOTHETICAL_OR_GENERAL_LANGUAGE_PRESENT")
                if _NEGATION.search(text):
                    labels.append("NEGATION_OR_RESOLUTION_LANGUAGE_PRESENT")
                regulatory.append(_excerpt(document, block, section, labels))
    body = {"record_type": "LEGAL_REGULATORY_SOURCE_CANDIDATES",
            "document_id": document["text_document_id"],
            "source_reference_id": document["source_reference_id"], "checked_ranges": ranges,
            "coverage_status": "INCOMPLETE" if reasons else "LOCAL_REQUESTED_RANGES_SCANNED",
            "coverage_reasons": reasons, "note_references": references,
            "semantic_scope_completeness_asserted": False,
            **({"audit_report_scope": {**audit, "excluded_blocks": sorted(excluded),
                                       "basis": "APPROVED_SOURCE_IS_ITEM_3_LEGAL_"
                                                "PROCEEDINGS_AND_CONTINGENCIES_NOTES"}}
               if excluded else {}),
            "D02": {"finding_status": "SOURCE_EXCERPTS_FOUND" if legal
                    else "NO_SUPPORTED_SOURCE_LANGUAGE", "candidates": legal,
                    "interpretation": "VERBATIM_LEGAL_DISCLOSURES_NOT_TOTAL_CASE_OR_LIABILITY_ASSERTION"},
            "D03": {"finding_status": "SOURCE_LANGUAGE_FOUND" if regulatory
                    else "NO_MATCHED_SOURCE_LANGUAGE", "candidates": regulatory,
                    "semantic_review_required": True, "actual_investigation_asserted": False},
            "not_disclosed_confirmed": False, "native_result_created": False,
            "publication_credit": False}
    return {**body, "policy_hash": _POLICY_HASH,
            "proposal_id": content_hash(value={**body, "policy_hash": _POLICY_HASH})}


def _width(scope):
    return scope["end_block_exclusive"] - scope["start_block"]


# One execution prepares the same source set twice: once to build the candidate
# and once to rebuild it inside build_text_evidence. Counted by (parser, source
# bytes, parameters), that is six of the ten parse calls a D02 position makes -
# build_text_document, reported_legal_fact_candidates and _bound_source twice
# each with identical parameters, plus two of the four parse_accession_xbrl_source
# calls. The remaining two are inside the frozen preparation and stay.
#
# The second preparation exists to re-derive the candidate independently, and
# that is kept: the candidate is still derived twice, from a parse of the same
# immutable bytes. What is not kept is parsing those bytes again, which is a
# deterministic function of them. The reuse is explicit, process-local and
# scoped to one `with` block; nothing reuses anything outside it, so a cold
# replay in a new process re-parses from the original evidence as before.
_SHARED_SOURCES = ContextVar("historical_text_shared_sources", default=None)


@contextmanager
def shared_source_preparation():
    """Reuse one prepared source set inside one execution, never across them.

    Not a cache of "this material is valid". The key carries the metric, the
    calculation target, every source reference and the SHA-256 of every raw
    byte string, so the same bytes claimed for a different period, entity or
    scope are a different key and the frozen identity checks run again. What is
    reused is the product of parsing exact bytes with exact parameters.
    """
    existing = _SHARED_SOURCES.get()
    if existing is not None:
        # Re-entrant on purpose. A Run creation opens the scope and the text
        # execution inside it opens one too; binding a fresh dict there would
        # hide the outer entries and drop its own on exit, which is what left
        # five real preparations in a creation that should need one.
        yield
        return
    token = _SHARED_SOURCES.set({})
    try:
        yield
    finally:
        _SHARED_SOURCES.reset(token)


# Every argument the frozen preparation takes, so the key is derived from all
# of them rather than from a list kept by hand. The first version named four
# and left out raw_blobs, which is where the original records live: a hit
# returned before the frozen function could run, so a request whose raw_blobs
# had been emptied - the state that makes the frozen function refuse with
# TEXT_V2_ORIGINAL_SOURCE_MISSING - was served from the cache instead.
# Declaring the set means the next argument added to the frozen signature
# stops the key rather than being silently left out of it.
PREPARATION_ARGUMENTS = frozenset({"target", "source_references", "raw_blobs",
                                   "raw_bytes_by_id", "source_filings"})
_BYTE_ARGUMENTS = ("raw_bytes_by_id",)


def _preparation_key(*, metric_id, source_arguments):
    """The inputs a prepared source set is a deterministic function of.

    Hashing the bytes rather than trusting ``raw_asset_id`` is deliberate: the
    id is supplied by the caller, and a key that trusts a caller-supplied
    identity is a key that can be made to collide. Everything else goes in as
    given, including the original records, because those are what the frozen
    preparation checks and what it derives the document from.
    """
    _need(set(source_arguments) == PREPARATION_ARGUMENTS,
          "HISTORICAL_TEXT_SHARED_KEY_ARGUMENTS_CHANGED:"
          + ",".join(sorted(set(source_arguments) ^ PREPARATION_ARGUMENTS)))
    keyed = {name: value for name, value in source_arguments.items()
             if name not in _BYTE_ARGUMENTS}
    keyed["raw_bytes"] = {asset_id: sha256_bytes(content=raw) for asset_id, raw
                          in sorted(source_arguments["raw_bytes_by_id"].items())}
    return content_hash(value={"metric_id": metric_id, **keyed})


def prepare_business_text_sources(*, metric_id, **source_arguments):
    """The frozen source preparation with the located ranges corrected.

    The frozen function owns source identity, period, the reported fact
    inventory and every other check. This re-runs only the excerpt scan, and
    only when a boundary actually falls inside a located range, so a filing
    without one returns the frozen record set unchanged.
    """
    _need(metric_id in SUPPORTED_METRICS,
          "HISTORICAL_TEXT_BOUNDARY_METRIC_NOT_WIRED:" + str(metric_id))
    shared = _SHARED_SOURCES.get()
    key = None if shared is None else _preparation_key(metric_id=metric_id,
                                                       source_arguments=source_arguments)
    if key is not None and key in shared:
        # A fresh copy every time. The frozen candidate builder walks these
        # structures and the caller owns what it is handed, so returning the
        # stored object would let one caller's edit reach the next one.
        return copy.deepcopy(shared[key])
    prepared = frozen.prepare_business_text_sources(metric_id=metric_id, **source_arguments)
    _need(len(prepared["documents"]) == 1, "HISTORICAL_TEXT_BOUNDARY_EXPECTS_ONE_DOCUMENT")
    reference_id = next(iter(prepared["documents"]))
    document = prepared["documents"][reference_id]
    corrected = narrow_document_sections(document=document)
    proposal = referenced_note_candidates(
        document=corrected,
        raw_bytes=source_arguments["raw_bytes_by_id"][corrected["raw_asset_id"]])
    if corrected is document and proposal == prepared["proposals"][reference_id]:
        # Neither correction changed anything on this filing, so the frozen
        # record set is returned as it stands rather than rebuilt to equal it.
        return _remember(shared=shared, key=key, prepared=prepared)
    _need(proposal["coverage_status"] == "LOCAL_REQUESTED_RANGES_SCANNED",
          "HISTORICAL_TEXT_BOUNDARY_NAVIGATION_INCOMPLETE:" + str(proposal["coverage_reasons"]))
    _need(proposal["D02"]["candidates"], "HISTORICAL_TEXT_BOUNDARY_LEAVES_NO_DISCLOSURE_TEXT")
    coverage = {key: value for key, value in prepared["coverages"][reference_id].items()
                if key != "coverage_hash"}
    coverage["document_id"] = corrected["text_document_id"]
    coverage["ranges"] = proposal["checked_ranges"]
    coverage["note_references"] = proposal["note_references"]
    coverage["section_boundary_policy"] = SECTION_BOUNDARY_POLICY
    coverage["coverage_hash"] = content_hash(value=coverage)
    return _remember(shared=shared, key=key, prepared={
        **prepared,
        "documents": {**prepared["documents"], reference_id: corrected},
        "coverages": {**prepared["coverages"], reference_id: coverage},
        "proposals": {**prepared["proposals"], reference_id: proposal}})


def _remember(*, shared, key, prepared):
    """Store a copy and hand back a copy, so neither side can reach the other."""
    if key is not None:
        shared[key] = copy.deepcopy(prepared)
    return prepared


def create_deterministic_text_candidate(*, compiled_spec, **source_arguments):
    prepared = prepare_business_text_sources(
        metric_id=compiled_spec["compiled"]["metric_id"], **source_arguments)
    return frozen._derive_candidate(compiled_spec=compiled_spec,
                                    target=source_arguments["target"], prepared=prepared)


def build_text_evidence(*, compiled_spec, candidate, **source_arguments):
    """Independently reconstruct the exact complete supported excerpt set."""
    prepared = prepare_business_text_sources(
        metric_id=compiled_spec["compiled"]["metric_id"], **source_arguments)
    expected = frozen._derive_candidate(compiled_spec=compiled_spec,
                                        target=source_arguments["target"], prepared=prepared)
    _need(validate_record(record=candidate) == expected, "TEXT_V2_CANDIDATE_REPLAY_CHANGED")
    checks, normalized, seen = [], {}, set()
    for role, claim in sorted(candidate["selected"].items(), key=lambda pair: pair[1]["order"]):
        sid = claim["source_reference_id"]
        doc = prepared["documents"][sid]
        index = claim["block_index"]
        _need((sid, index) not in seen, "TEXT_V2_DUPLICATE_EXCERPT")
        seen.add((sid, index))
        _need(any(r["section_id"] == claim["section_id"]
                  and r["start_block"] <= index < r["end_block_exclusive"]
                  for r in prepared["coverages"][sid]["ranges"]),
              "TEXT_V2_EXCERPT_OUTSIDE_SOURCE_RANGE")
        raw = source_arguments["raw_bytes_by_id"][doc["raw_asset_id"]]
        _need(sha256_bytes(content=raw[claim["raw_start_byte"]:claim["raw_end_byte"]])
              == claim["raw_span_sha256"], "TEXT_V2_RAW_SPAN_REPLAY_CHANGED")
        normalized[role] = claim["text"]
        checks.append({"check": "TEXT_EXACT_EXCERPT:" + role, "status": "PASS",
                       "claim_hash": content_hash(value=claim)})
    target = source_arguments["target"]
    body = {"candidate_hash": candidate["candidate_hash"], "status": "PASS",
            "normalized_values": normalized,
            "checks": [{"check": "TEXT_V2_SOURCE_COVERAGE_AND_TIME", "status": "PASS",
                        "coverage": list(prepared["coverages"].values())}] + checks,
            "reason_codes": [], "identity_constraints": [],
            "normalized_scope": dict(target["scope"]),
            "system_approval_eligible": True, "unresolved_scope_dimensions": []}
    return validate_record(record={"record_type": "EVIDENCE_CHECK",
                                   "evidence_check_id": content_hash(value=body), **body})


def reviewed_text_observations(*, compiled_spec, target, candidate, evidence_check, review_unit,
                               review_decisions, **source_arguments):
    from .observations import _build_text_observation
    from .review import effective_review_decision
    expected = build_text_evidence(compiled_spec=compiled_spec, target=target,
                                   candidate=candidate, **source_arguments)
    _need(validate_record(record=evidence_check) == expected, "TEXT_V2_EVIDENCE_REPLAY_CHANGED")
    unit = validate_record(record=review_unit)
    expected_unit, _ = build_text_review_unit(
        compiled_spec=compiled_spec, candidate=candidate, evidence_check=expected,
        source_bindings=source_arguments["source_references"])
    _need(unit == expected_unit, "TEXT_V2_REVIEW_BINDING_CHANGED")
    decision = effective_review_decision(review_unit=unit, decisions=review_decisions)
    _need(decision["decision"] == "APPROVE" and decision["reviewer_type"] in {"HUMAN", "SYSTEM"}
          and decision["approved_claims"] == target["scope"],
          "TEXT_V2_EFFECTIVE_APPROVAL_REQUIRED")
    sources = {s["source_reference_id"]: s for s in source_arguments["source_references"]}
    coverages = {r["source_reference_id"]: r for r in expected["checks"][0]["coverage"]}
    observations = []
    for role, claim in sorted(candidate["selected"].items(), key=lambda pair: pair[1]["order"]):
        source = sources[claim["source_reference_id"]]
        binding = {k: source[k] for k in ("raw_asset_id", "source_reference_id", "accession",
                                          "document_name", "source_role")}
        binding["text_binding"] = {
            "protocol": "TEXT_V1", "spec_closure_hash": compiled_spec["spec_closure_hash"],
            "candidate_hash": candidate["candidate_hash"],
            "review_unit_hash": unit["review_unit_hash"],
            "coverage_hash": coverages[source["source_reference_id"]]["coverage_hash"],
            **{key: claim[key] for key in ("extent", "document_id", "section_id", "block_index",
                                           "raw_start_byte", "raw_end_byte", "raw_span_sha256",
                                           "order")}}
        observations.append(_build_text_observation(
            metric_id=compiled_spec["compiled"]["metric_id"], semantic_role=role,
            company_id=target["company_id"], period_start=target["period_start"],
            period_end=target["period_end"], scope=target["scope"], value=claim["text"],
            source_binding=binding, approval_effect_hash=decision["approval_effect_hash"]))
    return observations


def replay_text_result(*, compiled_spec, target, company_traits, candidate, evidence_check,
                       review_unit, review_decisions, **source_arguments):
    from .calculator import calculate_text_metric
    observations = reviewed_text_observations(
        compiled_spec=compiled_spec, target=target, candidate=candidate,
        evidence_check=evidence_check, review_unit=review_unit,
        review_decisions=review_decisions, **source_arguments)
    result, trace = calculate_text_metric(compiled_spec=compiled_spec, target=target,
                                          company_traits=company_traits,
                                          observations=observations)
    return result, trace, observations


def text_api(metric_id):
    """Route the metrics this successor corrects here and the rest to the parent."""
    if metric_id in SUPPORTED_METRICS:
        from . import historical_text_results
        return historical_text_results, build_text_review_unit
    from .normal_run_v3 import text_api as parent_api
    return parent_api(metric_id)
