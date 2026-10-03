"""A proxy statement's identity when it carries no inline XBRL.

Purpose:
    The frozen governance reader (``text_business_candidates._bound_source``)
    identifies a proxy by its DEI facts: EntityCentralIndexKey must be the
    registrant's CIK and DocumentType the filing's form, and the registrant's
    name comes from EntityRegistrantName. Proxy statements carried inline XBRL
    only once the pay-versus-performance rule required it, so the proxies
    filed in 2022 - the ones that first report fiscal 2021, and fiscal 2022
    for registrants whose year ends in January - have none. All eight such
    proxies the acquisition saved stop in the frozen parser with
    ``XBRL source contains no contexts``, and C02 had no answer for any of
    those periods, as an unnamed error rather than a named one.

    The filing is still bound: the frozen reader checks the stored bytes, the
    record's accession, document and URL before it parses, and the URL is
    built from the registrant's CIK and the accession the submissions index
    lists for that CIK. What the DEI facts added was the form and the name.
    Each of these proxies prints both on its Schedule 14A cover: the box
    against "Definitive Proxy Statement" is checked and every other box is
    not, and the registrant's name stands above "(Name of Registrant as
    Specified In Its Charter)". That is what this successor reads, and the
    name it reads must be a name the SEC's own submissions record gives this
    CIK on the proxy's filing date (``cover_name_in_effect``), compared
    without legal suffixes or state tags. Not the annual report's DEI name:
    measured on the eight proxies, three would fail that for reasons that are
    not identity - the SEC's conformed name ("FORD MOTOR CO", "MARRIOTT
    INTERNATIONAL INC /MD/") beside the charter name, and a rename between
    the annual report and the proxy (ViacomCBS became Paramount Global in
    February 2022; the record dates the change). The record's dates are what
    make this a check: Salesforce's proxy, filed four weeks after its rename,
    matches the new name and would not match the old one.

    Nothing changes for a proxy that carries inline XBRL: the frozen reader
    answers, and only the exact no-contexts error on a document with no
    inline XBRL at all reaches the cover. A document that has inline markup
    and still fails the parse is broken, not older, and keeps its error.

    The checkbox glyphs are the ones these filings use (a ballot box with an
    X or a check for checked; an empty ballot box or Wingdings' ``¨`` for
    unchecked, with Wingdings' ``x`` for checked beside it; Wingdings' ``þ``
    and ``o``, a checked and an empty box, on JPMorgan's). Another glyph is
    refused by name rather than guessed, and the cover layout is refused by
    name when the name does not stand in its own block above the caption.

    One later-acquired proxy prints its name above the caption as a logo
    image with a file name for alt text, so no text stands there. For that
    layout only - the slot holds an image and nothing else, and the filer
    caption follows the name caption - the name read is the first block the
    filing prints after its cover, skipping the form's fee lines and links;
    JPMorgan's 2022 proxy prints its own name there, above its address. The
    check is unchanged: ``cover_name_in_effect`` accepts that block only when
    it is a name the SEC record gives the CIK on the filing date, so a block
    that is not the name is refused, never taken. The identity records
    ``cover_name_basis`` for this layout and only for it, so the eight covers
    that print their name keep their records byte for byte.

Call relationships:
    ``historical_text_input`` reads the cover of a C02 proxy without inline
    XBRL and checks its name (``cover_name_in_effect``) when it admits the
    sources, which the historical Run repeats on every replay.
    ``historical_text_results`` prepares C02 through
    ``release_aware_with(text_results_v2.prepare_business_text_sources,
    governance_source_document=governance_source_document)`` and then calls
    ``record_cover_identity`` on what it returns.
"""
from __future__ import annotations

import re

from .canonical import content_hash
from .deterministic_router import DeterministicRouterError
from .historical_board_composition_v3 import _name_core
from .historical_dei import release_aware, release_aware_with
from . import text_business_candidates as _frozen
from .text_coverage import _Blocks

NO_CONTEXTS = "XBRL source contains no contexts"
IDENTITY_BASIS = "PROXY_SCHEDULE_14A_COVER"
CHECKED = frozenset({"☒", "☑", "x", "þ"})
UNCHECKED = frozenset({"☐", "¨", "o"})
OPTIONS = {
    "PRELIMINARY": r"Preliminary Proxy Statement",
    "CONFIDENTIAL": r"Confidential,\s*for Use of the Commission Only",
    "DEFINITIVE": r"Definitive Proxy Statement",
    "ADDITIONAL": r"Definitive Additional Materials",
    "SOLICITING": r"Soliciting Material",
}
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))
_NAME_CAPTION = "(name of registrant as specified in its charter)"
_FILER_CAPTION = "(name of person(s) filing proxy statement, if other than the registrant)"
NAME_AS_IMAGE = "NAME_PRINTED_AS_AN_IMAGE_FIRST_BLOCK_AFTER_THE_COVER"
_FEE_LINE = re.compile(r"payment of filing fee|\(?\d\)\s|\S\s*(?:no fee required|fee computed"
                       r"|fee paid previously|check box if any part of the fee)", re.I)
_frozen_bound_source = release_aware(_frozen._bound_source)


class HistoricalProxyIdentityError(ValueError):
    """The proxy's cover does not establish its form and registrant."""


def _need(condition, reason, category="IMPLEMENTATION_GAP"):
    """A cover this reader cannot read is an implementation gap unless the
    caller names it otherwise; a name that is not this registrant's is not."""
    if not condition:
        error = HistoricalProxyIdentityError(reason)
        error.category = category
        raise error


def carries_inline_xbrl(raw_bytes):
    """Whether the document holds any inline XBRL element at all."""
    return b"<ix:" in raw_bytes.lower()


def _clean(text):
    return " ".join(text.translate(_ZERO_WIDTH).split())


def proxy_cover(*, raw_bytes, filing):
    """The form and registrant a definitive proxy's Schedule 14A cover states.

    Returns the registrant's name as printed and the mark against each box.
    """
    _need(filing["form"] == "DEF 14A", "HISTORICAL_PROXY_COVER_FORM_NOT_DEF14A:" + str(filing["form"]))
    _need(not carries_inline_xbrl(raw_bytes), "HISTORICAL_PROXY_COVER_ON_INLINE_DOCUMENT")
    text = raw_bytes.decode("utf-8-sig")
    parser = _Blocks(text)
    parser.feed(text)
    parser.close()
    parser._flush()
    parsed = [(block, clean) for block, clean in ((block, _clean(block["text"])) for block in parser.blocks)
              if clean]
    blocks = [clean for _, clean in parsed]
    folded = [block.casefold() for block in blocks]
    _need("schedule 14a" in folded, "HISTORICAL_PROXY_COVER_SCHEDULE_14A_NOT_FOUND")
    start = folded.index("schedule 14a")
    captions = [index for index, block in enumerate(folded) if _NAME_CAPTION in block]
    _need(bool(captions) and captions[0] > start + 1, "HISTORICAL_PROXY_COVER_NAME_CAPTION_NOT_FOUND")
    caption = captions[0]
    _need(folded[caption] == _NAME_CAPTION, "HISTORICAL_PROXY_COVER_NAME_LAYOUT_UNSUPPORTED")
    name, basis, boxes_end = blocks[caption - 1], None, caption - 1
    if any(re.search(pattern, name, re.I) for pattern in OPTIONS.values()):
        # No text stands above the caption. When the slot holds an image, the
        # name is the first block the filing prints after its cover.
        name, basis, boxes_end = _name_after_an_image_cover(text=text, parsed=parsed, caption=caption), \
            NAME_AS_IMAGE, caption
    _need(re.search(r"[A-Za-z]", name) is not None and len(name) <= 200
          and not any(re.search(pattern, name, re.I) for pattern in OPTIONS.values()),
          "HISTORICAL_PROXY_COVER_NAME_NOT_ESTABLISHED")
    boxes = " ".join(blocks[start + 1:boxes_end])
    marks = {}
    for option, pattern in OPTIONS.items():
        found = [match.group("mark") for match in
                 re.finditer(r"(?:^|(?<=\s))(?P<mark>\S)\s*" + pattern, boxes, re.I)]
        _need(len(found) == 1, "HISTORICAL_PROXY_COVER_BOX_NOT_UNIQUE:" + option + ":" + str(len(found)))
        _need(found[0] in CHECKED | UNCHECKED,
              "HISTORICAL_PROXY_COVER_CHECKBOX_GLYPH_UNRECOGNIZED:" + option + ":U+%04X" % ord(found[0]))
        marks[option] = found[0]
    _need(marks["DEFINITIVE"] in CHECKED
          and all(mark in UNCHECKED for option, mark in marks.items() if option != "DEFINITIVE"),
          "HISTORICAL_PROXY_COVER_DEFINITIVE_BOX_NOT_THE_ONLY_CHECKED:"
          + ",".join(option for option, mark in sorted(marks.items()) if mark in CHECKED))
    cover = {"registrant_name": name, "marks": marks}
    if basis is not None:
        cover["name_basis"] = basis
    return cover


def _name_after_an_image_cover(*, text, parsed, caption):
    """The first block a cover whose name slot is an image is followed by.

    The slot must hold an image and no text, and the filer caption must follow
    the name caption, as the form prints them. The fee lines the form prints
    after that caption, and links (a table of contents), are skipped; the next
    block is returned as printed. It is not taken as the registrant's name here:
    ``cover_name_in_effect`` accepts it only when it is a name the SEC record
    gives the CIK on the filing date, so a block that is not the name is
    refused by name rather than taken.
    """
    slot = text[parsed[caption - 1][0]["end"]:parsed[caption][0]["start"]]
    _need(re.search(r"<img\b", slot, re.I) is not None
          and not re.sub(r"<[^>]*>|&nbsp;|&#160;|\s", "", slot),
          "HISTORICAL_PROXY_COVER_NAME_NOT_ESTABLISHED")
    _need(caption + 1 < len(parsed) and parsed[caption + 1][1].casefold() == _FILER_CAPTION,
          "HISTORICAL_PROXY_COVER_FILER_CAPTION_NOT_FOUND")
    for block, clean in parsed[caption + 2:]:
        if block["linked"] or _FEE_LINE.match(clean):
            continue
        return clean
    _need(False, "HISTORICAL_PROXY_COVER_NAME_NOT_ESTABLISHED")


def proxy_bound_source(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    """``_bound_source`` for C02's proxy: the frozen reader, then the cover.

    The frozen reader runs first and answers whenever it can. Its record,
    byte and URL checks come before its XBRL parse, so reaching the parse's
    no-contexts error means they passed; only then, and only for a document
    with no inline markup, is the cover read in place of the DEI facts. The
    parsed facts and their metadata are returned as ``None``: the governance
    document reads only the names.
    """
    try:
        return _frozen_bound_source(raw_bytes=raw_bytes, raw_blob=raw_blob,
                                    source_reference=source_reference,
                                    company_id=company_id, cik=cik, filing=filing)
    except DeterministicRouterError as error:
        if str(error) != NO_CONTEXTS or carries_inline_xbrl(raw_bytes):
            raise
    cover = proxy_cover(raw_bytes=raw_bytes, filing=filing)
    return None, None, [cover["registrant_name"]]


governance_source_document = release_aware_with(_frozen.governance_source_document,
                                                _bound_source=proxy_bound_source)


def sec_names_in_effect(*, inventory, on_date):
    """The names the SEC's submissions record gives this CIK on ``on_date``.

    A former name counts on the days its interval covers. The current name
    counts from the end of the last former name that is a different name -
    the record carries the registrant's own spelling as a former name too,
    so a former entry equal to the current one is not a rename.
    """
    current, former = inventory["name"], inventory.get("formerNames") or []
    names = {entry["name"] for entry in former
             if entry["from"][:10] <= on_date <= entry["to"][:10]}
    renamed = [entry["to"][:10] for entry in former
               if _name_core(entry["name"]) != _name_core(current)]
    if not renamed or on_date >= max(renamed):
        names.add(current)
    return sorted(names)


def cover_name_in_effect(*, cover, inventory, filing):
    """Require the cover's name to be one the SEC record gives the CIK that day."""
    names = sec_names_in_effect(inventory=inventory, on_date=filing["filingDate"])
    _need(_name_core(cover["registrant_name"]) in {_name_core(name) for name in names},
          "HISTORICAL_PROXY_COVER_REGISTRANT_NOT_THE_SEC_NAME_ON_FILING_DATE",
          category="SOURCE_INTEGRITY_ERROR")
    identity = {"basis": IDENTITY_BASIS, "cover_registrant_name": cover["registrant_name"],
                "sec_names_on_filing_date": names, "filing_date": filing["filingDate"]}
    if "name_basis" in cover:
        identity["cover_name_basis"] = cover["name_basis"]
    return identity


def record_cover_identity(*, prepared, raw_bytes_by_id):
    """Record in the governance coverage that the proxy was identified by its cover.

    A proxy identified by its DEI facts is returned unchanged. The name check
    belongs to the input admission (``cover_name_in_effect``), which has the
    submissions record; this only makes the basis visible to a reader of the
    Evidence.
    """
    documents, coverages = prepared["documents"], prepared["coverages"]
    annual = [sid for sid, coverage in coverages.items()
              if coverage.get("scope") == "ORDINARY_ANNUAL_IDENTITY_ANCHOR_ONLY"]
    governance = [sid for sid in documents if sid not in annual]
    _need(len(annual) == 1 and len(governance) == 1, "HISTORICAL_PROXY_IDENTITY_SOURCE_SET_UNEXPECTED")
    governance_id = governance[0]
    document = documents[governance_id]
    if (document["source_filing"]["form"] != "DEF 14A"
            or carries_inline_xbrl(raw_bytes_by_id[document["raw_asset_id"]])):
        return prepared
    coverage = {key: value for key, value in coverages[governance_id].items() if key != "coverage_hash"}
    coverage["governance_identity"] = {"basis": IDENTITY_BASIS,
                                       "cover_registrant_names": document["registrant_names"]}
    coverage["coverage_hash"] = content_hash(value=coverage)
    return {**prepared, "coverages": {**coverages, governance_id: coverage}}
