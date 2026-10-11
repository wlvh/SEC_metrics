"""Mechanical SEC proxy identity for an explicitly selected no-inline source.

Cover reading and dated names are retained from bcc0c0bc. This path checks
original records/bytes/issuer URL directly and shares visible-block parsing;
it does not import a historical bytecode view, C02 selector or Run registry.
"""
import re
from .canonical import content_hash, sha256_bytes
from .records import validate_record
from .resource_limits import RESOURCE_LIMITS
from .sources import validate_public_sec_filing_identity
from .text_coverage import _Blocks, _byte_offsets
from .organization_name_core import _name_core

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


class ProxySourceIdentityError(ValueError):
    """The proxy's cover does not establish its form and registrant."""


def validate_proxy_source(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    """Check original bytes and the selected issuer/document without parsing XBRL."""
    blob=validate_record(record=dict(raw_blob));ref=validate_record(record=dict(source_reference))
    _need(type(raw_bytes) is bytes and 0<len(raw_bytes)<=RESOURCE_LIMITS.max_html_bytes,
          'PROXY_SOURCE_SIZE_INVALID','SOURCE_INTEGRITY_ERROR')
    _need(blob['record_type']=='RAW_BLOB' and ref['record_type']=='SOURCE_REFERENCE'
          and blob['media_type']=='text/html' and blob['byte_length']==len(raw_bytes)
          and blob['raw_asset_id']==ref['raw_asset_id']=='sha256:'+sha256_bytes(content=raw_bytes),
          'PROXY_SOURCE_BYTES_CHANGED','SOURCE_INTEGRITY_ERROR')
    _need(ref['company_id']==company_id and ref['source_role']=='governance_proxy'
          and ref['accession']==filing['accessionNumber']
          and ref['document_name']==filing['primaryDocument'],
          'PROXY_SELECTED_REFERENCE_CHANGED','SOURCE_INTEGRITY_ERROR')
    validate_public_sec_filing_identity(raw_blob=blob,source_url=ref['source_url'],
        accession=ref['accession'],document_name=ref['document_name'],source_role='target_primary',
        allowed_ciks=[str(int(cik))])
    _need(filing['form']=='DEF 14A','PROXY_SOURCE_FORM_NOT_DEF14A','SOURCE_INTEGRITY_ERROR')
    return blob,ref


def governance_source_document(*, raw_bytes, raw_blob, source_reference, company_id, cik, filing):
    """Retain the existing whole visible proxy document and byte locators."""
    validate_proxy_source(raw_bytes=raw_bytes,raw_blob=raw_blob,source_reference=source_reference,
                          company_id=company_id,cik=cik,filing=filing)
    cover=proxy_cover(raw_bytes=raw_bytes,filing=filing)
    text=raw_bytes.decode('utf-8-sig')
    parser=_Blocks(text);parser.feed(text);parser.close();parser._flush()
    reasons=list(parser.structural_errors)
    if (parser.html_count,parser.body_count,parser.html_closed,parser.body_closed)!=(1,1,1,1) or parser.stack:
        reasons.append('GOVERNANCE_TEXT_DOCUMENT_INCOMPLETE')
    blocks=parser.blocks
    offsets=_byte_offsets(text,[v for b in blocks for v in (b['start'],b['end'])])
    bom=3 if raw_bytes.startswith(b'\xef\xbb\xbf') else 0
    for i,block in enumerate(blocks):
        block['block_index']=i
        block['raw_start_byte']=offsets[block.pop('start')]+bom
        block['raw_end_byte']=offsets[block.pop('end')]+bom
        block['raw_span_sha256']=sha256_bytes(content=raw_bytes[block['raw_start_byte']:block['raw_end_byte']])
        block.pop('leading_emphasis',None)
    body={'record_type':'GOVERNANCE_SOURCE_TEXT_DOCUMENT','company_id':company_id,
          'cik':str(int(cik)),'source_reference_id':source_reference['source_reference_id'],
          'raw_asset_id':raw_blob['raw_asset_id'],'source_filing':dict(filing),
          'registrant_names':[cover['registrant_name']],
          'source_state':'INCOMPLETE' if reasons else 'COMPLETE_LOCAL_DOCUMENT',
          'source_reasons':sorted(set(reasons)),'blocks':blocks,
          'board_measurement_date_assigned':False,'publication_credit':False}
    return {**body,'text_document_id':content_hash(value=body)}


def _need(condition, reason, category="IMPLEMENTATION_GAP"):
    """A cover this reader cannot read is an implementation gap unless the
    caller names it otherwise; a name that is not this registrant's is not."""
    if not condition:
        error = ProxySourceIdentityError(reason)
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
