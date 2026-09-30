"""Read underline as a heading mark, beside the bold one the frozen parser has.

``text_coverage._Blocks`` treats only ``<b>``/``<strong>``/``<h1>``-``<h6>`` and
``font-weight >= 600`` as emphasis, and D01 delivers a block's leading run of
emphasised parts. A registrant who marks headings with underline therefore
loses them, and the result says nothing about it.

Measured on this repository's filings before writing any of this. Marriott
marks its two top-level risk groups ``font-weight:700`` and its four
second-level ones ``font-weight:400`` plus ``text-decoration:underline``,
inside the same ``<div style="margin-top:9pt;text-indent:22.5pt">`` wrapper and
the same 10pt face - so one document marks one structural level two ways and
the result carries one of them. Its Item 1A delivers 34, 35 and 33 headings for
2025, 2024 and 2023 where the filing has 38, 39 and 37. Across the nine
readable filings it is the only one that uses the style, and every block it
uses it on is a risk-category heading.

Underline is tracked on its own stack rather than folded into the frozen flag.
A rule that simply sets the flag on ``underline`` and clears it on ``none``
cannot tell which contribution it is clearing: measured, it clears 1,599 bold
leading emphases in one saved document alone. Two stacks make ``none`` cancel
an underline and nothing else.

The bold stack restates the frozen ``font-weight`` rule, which is a second copy
of a rule and is held to the original mechanically: with
``admit_underline=False`` this parser must produce blocks identical to the
frozen one, which ``tests/vnext/test_historical_text_emphasis.py`` requires on
every saved filing.

The document builder does not restate ``build_text_document``. It runs the
frozen one for all of its identity validation, its period checks and its
section boundaries - section boundaries do not depend on emphasis, since
``_heading`` reads ``linked`` and text only - and then replaces the two
emphasis fields, requiring every other per-block field to be identical. That
requirement is what makes this provably a one-field change rather than a second
parser.

One further change, also D01's alone. The frozen flush ends a block's leading
emphasis at the first unemphasised part, which keeps a bold lead sentence apart
from its paragraph. Paramount sets the two periods of "U.S." at weight 400
between bold letters, so its heading "Failures to comply with or changes in
U.S. or foreign laws..." was delivered as "Failures to comply with or changes
in U". An unemphasised part of one or two punctuation characters is therefore
bridged when the next visible part is emphasised again - and only then, so the
ordinary lead sentence, whose unemphasised part is the paragraph, still ends
where it did. Measured on all eleven D01 positions before writing it: this
line is the only heading that moves; 26 of Ford's 30 and 32 of Marriott's
headings are lead sentences and none of them resumes after its gap.
Elsewhere in the same documents it joins a bold caption to its bold
continuation across an unbolded separator - "Note 7A, 7B", "Item 7. Management's
Discussion..." - none of which is in Item 1A.

It is D01's alone. D02 and C02 keep the frozen parser, so nothing they select
moves and ``audit_report_spans`` never sees an underline-marked block. That
boundary is deliberate: admitting underline on the shared route was measured
too, and it opens an audit-report exclusion on Southwest's hyperlinked index
line that swallows 849 blocks including five confirmed legal-contingency ones.
The sibling rule's own ``not linked`` check would close that, but neither is
needed while the successor parser stays on this route.
"""
from __future__ import annotations

import re

from .canonical import content_hash, sha256_bytes
from .historical_dei import release_aware
from .text_coverage import (TextCoverageError, _Blocks, _byte_offsets,
                            build_text_document)

# The frozen readers this module calls, answering the DEI namespace question
# for every taxonomy release (historical_dei).
build_text_document = release_aware(build_text_document)

_WEIGHT = re.compile(r"(?:^|;)\s*font-weight\s*:\s*([^;]+)", re.I)
_DECORATION = re.compile(r"(?:^|;)\s*text-decoration[^:]*:\s*([^;]+)", re.I)
_BOLD_TAGS = {"b", "strong", "h1", "h2", "h3", "h4", "h5", "h6"}
_CANCELS_UNDERLINE = {"none", "initial", "unset"}
# An unemphasised part the leading emphasis may cross, when emphasis resumes
# right after it: one or two characters, none a letter, digit or space.
_BRIDGE = re.compile(r"[^\w\s]{1,2}")
# Every per-block field the successor must leave exactly as the frozen parser
# produced it. The two emphasis fields are the only ones it may change.
UNCHANGED_BLOCK_FIELDS = ("block_index", "text", "linked", "raw_start_byte",
                          "raw_end_byte", "raw_span_sha256")
EMPHASIS_FIELDS = ("emphasized", "leading_emphasis")
# What may lie between the two halves of a heading the filing runs over a page:
# the page number and the linked "Table of Contents" line at the next page's
# head. Measured on Southwest's FY2022 and FY2023 reports, the only filings of
# the corpus where a heading runs over a page; nothing else is page furniture
# here, so a heading followed by any body text is never joined to anything.
_PAGE_NUMBER = re.compile(r"\d{1,3}")
_CONTENTS_LINK = "table of contents"
# A block that ends like this ends its sentence; a heading cut by a page does not.
_SENTENCE_END = re.compile(r"[.:;?!)\]\"\u201d\u2019]\s*$")


def _need(condition, reason):
    if not condition:
        raise TextCoverageError(reason)


class UnderlineBlocks(_Blocks):
    """The frozen block parser with an underline stack beside its flag."""

    def __init__(self, text, *, admit_underline=True, bridge_punctuation=True):
        super().__init__(text)
        self.admit_underline = admit_underline
        self.bridge_punctuation = bridge_punctuation
        # Index i + 1 corresponds to self.stack[i]; index 0 is the root.
        self._bold = [False]
        self._underline = [False]

    def _bold_for(self, tag, style):
        """The frozen font-weight rule, inheriting from the bold stack.

        Inheriting from the bold component rather than from the combined flag
        is the whole point of the second stack: it is what lets an underline be
        cancelled without taking a bold with it.
        """
        bold = self._bold[-1]
        if tag in _BOLD_TAGS:
            bold = True
        weight = _WEIGHT.search(style)
        if weight:
            token = weight[1].strip().casefold()
            if token in {"bold", "bolder"} or token.isdigit() and int(token) >= 600:
                bold = True
            elif token == "normal" or token.isdigit() and int(token) < 600:
                bold = False
        return bold

    def _underline_for(self, style):
        underline = self._underline[-1]
        found = _DECORATION.search(style)
        if found:
            token = found[1].strip().casefold()
            if "underline" in token:
                underline = True
            elif token in _CANCELS_UNDERLINE:
                underline = False
        return underline

    def handle_starttag(self, tag, attrs):
        style = dict(attrs).get("style", "")
        bold = self._bold_for(tag, style)
        underline = self._underline_for(style)
        depth = len(self.stack)
        super().handle_starttag(tag, attrs)
        if len(self.stack) == depth + 1:
            self._bold.append(bold)
            self._underline.append(underline)
            frame = self.stack[-1]
            self.stack[-1] = (frame[0], frame[1], frame[2],
                              bold or (underline and self.admit_underline))

    def _bridges(self, index):
        """Whether the unemphasised part at ``index`` sits inside a heading."""
        if not (self.bridge_punctuation and _BRIDGE.fullmatch(self.parts[index][2].strip())):
            return False
        following = next((part for part in self.parts[index + 1:] if part[2].strip()), None)
        return following is not None and bool(following[4])

    def _flush(self):
        """The frozen flush, with the punctuation bridge as its one change.

        Restated rather than wrapped, because the prefix is built inside the
        loop. With ``bridge_punctuation`` off it has to produce the frozen
        parser's blocks - the same guarantee the copied font-weight rule is
        held to.
        """
        if self.parts:
            value = " ".join("".join(p[2] for p in self.parts).split())
            if value:
                prefix = []
                for index, part in enumerate(self.parts):
                    if not part[2].strip() and not prefix:
                        continue
                    if not part[4] and part[2].strip():
                        if prefix and self._bridges(index):
                            prefix.append(part)
                            continue
                        break
                    prefix.append(part)
                prefix_text = " ".join("".join(p[2] for p in prefix).split())
                self.blocks.append({"text": value, "start": self.parts[0][0],
                                    "end": self.parts[-1][1],
                                    "linked": any(p[3] for p in self.parts),
                                    "emphasized": all(p[4] for p in self.parts
                                                      if p[2].strip()),
                                    "leading_emphasis": ({"text": prefix_text,
                                                          "start": prefix[0][0],
                                                          "end": prefix[-1][1]}
                                                         if prefix_text else None)})
            self.parts = []

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        # The frozen rule deletes a contiguous suffix of the stack, including
        # for an optional close, so the parallel stacks follow its length.
        wanted = len(self.stack) + 1
        del self._bold[wanted:]
        del self._underline[wanted:]


def build_text_document_admitting_underline(*, raw_bytes: bytes, raw_blob, source_reference,
                                            expected_company_id: str, expected_cik: str,
                                            expected_period_end: str) -> dict:
    """The frozen document, with underline admitted into its emphasis fields.

    Everything except the two emphasis fields comes from the frozen builder and
    is required to be unchanged, so a drift in the copied font-weight rule
    stops here rather than showing up as a different heading set.
    """
    document = build_text_document(raw_bytes=raw_bytes, raw_blob=raw_blob,
                                   source_reference=source_reference,
                                   expected_company_id=expected_company_id,
                                   expected_cik=expected_cik,
                                   expected_period_end=expected_period_end)
    text = raw_bytes.decode("utf-8-sig", errors="strict")
    parser = UnderlineBlocks(text)
    parser.feed(text)
    parser.close()
    parser._flush()
    blocks = parser.blocks
    _need(len(blocks) == len(document["blocks"]),
          "HISTORICAL_EMPHASIS_BLOCK_COUNT_CHANGED")
    bom_size = 3 if raw_bytes.startswith(b"\xef\xbb\xbf") else 0
    positions = [position for block in blocks for position in (block["start"], block["end"])]
    positions += [position for block in blocks if block["leading_emphasis"]
                  for position in (block["leading_emphasis"]["start"],
                                   block["leading_emphasis"]["end"])]
    offsets = _byte_offsets(text, positions)
    for index, block in enumerate(blocks):
        block["block_index"] = index
        block["raw_start_byte"] = offsets[block.pop("start")] + bom_size
        block["raw_end_byte"] = offsets[block.pop("end")] + bom_size
        block["raw_span_sha256"] = sha256_bytes(
            content=raw_bytes[block["raw_start_byte"]:block["raw_end_byte"]])
        prefix = block["leading_emphasis"]
        if prefix:
            prefix["raw_start_byte"] = offsets[prefix.pop("start")] + bom_size
            prefix["raw_end_byte"] = offsets[prefix.pop("end")] + bom_size
            prefix["raw_span_sha256"] = sha256_bytes(
                content=raw_bytes[prefix["raw_start_byte"]:prefix["raw_end_byte"]])
    joined = join_headings_split_across_a_page(
        blocks=blocks, section=document["sections"].get("ITEM_1A"), raw_bytes=raw_bytes)
    for widened, frozen in zip(blocks, document["blocks"]):
        _need(set(widened) == set(frozen), "HISTORICAL_EMPHASIS_BLOCK_SHAPE_CHANGED")
        _need(all(widened[field] == frozen[field] for field in UNCHANGED_BLOCK_FIELDS),
              "HISTORICAL_EMPHASIS_CHANGED_MORE_THAN_THE_EMPHASIS_FIELDS")
    body = {key: value for key, value in document.items() if key != "text_document_id"}
    body["blocks"] = blocks
    # Only a document where a join happened carries the record, so every other
    # document is byte for byte what it was before this rule existed.
    if joined:
        body["headings_joined_across_a_page"] = joined
    return {**body, "text_document_id": content_hash(value=body)}


def _heading_only(block):
    prefix = block["leading_emphasis"]
    return prefix is not None and not block["linked"] and prefix["text"] == block["text"]


def _page_furniture(block):
    text = block["text"].strip()
    return (bool(_PAGE_NUMBER.fullmatch(text))
            or (block["linked"] and text.casefold() == _CONTENTS_LINK))


def join_headings_split_across_a_page(*, blocks, section, raw_bytes):
    """Join the two halves of a heading the filing runs over a page, in Item 1A.

    One heading is one line of D01. Southwest lets three risk-factor headings
    run over the foot of a page: the first half ends a block, the page number
    and the next page's linked "Table of Contents" line follow, and the rest
    opens the next page as its own bold block, beginning mid-sentence. The
    frozen selector takes every emphasised block as a heading, so the value
    listed each half as a line and neither line was the heading.

    A pair is joined only when all of these hold: both blocks are emphasised
    whole and not linked; only page furniture lies between them, and some does
    (the page break is what explains two blocks); the first does not end a
    sentence; the second begins with a lower-case letter. The last is what
    keeps a category label at the foot of a page apart from the heading that
    opens the next one - measured, two such pairs in the corpus (Enphase
    FY2025, Southwest FY2025), both left as two headings.

    The joined heading is recorded where it starts: the first block's leading
    emphasis carries both halves' text and a raw span from the first half's
    start to the second half's end, and the second block's leading emphasis is
    folded into it. Block text and every other field stay the frozen parser's.

    Returns the joins made, as ``{"first_block", "second_block",
    "furniture_blocks"}`` records.
    """
    if not section or section.get("status") != "LOCATED" or len(section["candidates"]) != 1:
        return []
    scope = section["candidates"][0]
    start, end = scope["start_block"], scope["end_block_exclusive"]
    joined, index = [], start
    while index < end:
        block = blocks[index]
        following = index + 1
        while following < end and _page_furniture(blocks[following]):
            following += 1
        if (_heading_only(block) and not _SENTENCE_END.search(block["text"])
                and index + 1 < following < end and _heading_only(blocks[following])
                and blocks[following]["text"][:1].islower()):
            second = blocks[following]
            first_prefix, second_prefix = block["leading_emphasis"], second["leading_emphasis"]
            raw_start, raw_end = first_prefix["raw_start_byte"], second_prefix["raw_end_byte"]
            block["leading_emphasis"] = {
                "text": block["text"] + " " + second["text"],
                "raw_start_byte": raw_start, "raw_end_byte": raw_end,
                "raw_span_sha256": sha256_bytes(content=raw_bytes[raw_start:raw_end])}
            second["leading_emphasis"] = None
            joined.append({"first_block": index, "second_block": following,
                           "furniture_blocks": list(range(index + 1, following))})
            index = following + 1
            continue
        index += 1
    return joined
