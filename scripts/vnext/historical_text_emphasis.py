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
from .text_coverage import (TextCoverageError, _Blocks, _byte_offsets,
                            build_text_document)

_WEIGHT = re.compile(r"(?:^|;)\s*font-weight\s*:\s*([^;]+)", re.I)
_DECORATION = re.compile(r"(?:^|;)\s*text-decoration[^:]*:\s*([^;]+)", re.I)
_BOLD_TAGS = {"b", "strong", "h1", "h2", "h3", "h4", "h5", "h6"}
_CANCELS_UNDERLINE = {"none", "initial", "unset"}
# Every per-block field the successor must leave exactly as the frozen parser
# produced it. The two emphasis fields are the only ones it may change.
UNCHANGED_BLOCK_FIELDS = ("block_index", "text", "linked", "raw_start_byte",
                          "raw_end_byte", "raw_span_sha256")
EMPHASIS_FIELDS = ("emphasized", "leading_emphasis")


def _need(condition, reason):
    if not condition:
        raise TextCoverageError(reason)


class UnderlineBlocks(_Blocks):
    """The frozen block parser with an underline stack beside its flag."""

    def __init__(self, text, *, admit_underline=True):
        super().__init__(text)
        self.admit_underline = admit_underline
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
    for widened, frozen in zip(blocks, document["blocks"]):
        _need(set(widened) == set(frozen), "HISTORICAL_EMPHASIS_BLOCK_SHAPE_CHANGED")
        _need(all(widened[field] == frozen[field] for field in UNCHANGED_BLOCK_FIELDS),
              "HISTORICAL_EMPHASIS_CHANGED_MORE_THAN_THE_EMPHASIS_FIELDS")
    body = {key: value for key, value in document.items() if key != "text_document_id"}
    body["blocks"] = blocks
    return {**body, "text_document_id": content_hash(value=body)}
