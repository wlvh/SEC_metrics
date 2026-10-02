"""Explicit D01 document view for underline and split-markup risk headings.

This is targeted reuse of #47's historical_text_emphasis.py at fixed commit
2b4f571e, with its historical DEI wrapper removed. The frozen builder still
authenticates source identity, period, sections and exact bytes. The successor
reparses only the heading emphasis, checks all other block fields against the
frozen document, and derives a new document identity. It is selected only by
the D01-emphasis input policy; C02/D02 and old D01 Runs keep their old parser.

Underline has its own stack so cancelling it never cancels bold. A one- or
two-character punctuation gap is crossed only when emphasis resumes, which
keeps a bold lead sentence separate from the following ordinary paragraph.
The current TEXT_V1 claim records one contiguous raw span. A known heading
split across a page cannot be represented as one verbatim excerpt under that
contract, so a page-number/Table of Contents/continuation pattern is withheld
until a separately reviewed multi-span successor exists.
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
    _need(not split_heading_requires_multispan(
        blocks=blocks, section=document["sections"].get("ITEM_1A")),
        "D01_MULTISPAN_HEADING_UNSUPPORTED")
    for widened, frozen in zip(blocks, document["blocks"]):
        _need(set(widened) == set(frozen), "HISTORICAL_EMPHASIS_BLOCK_SHAPE_CHANGED")
        _need(all(widened[field] == frozen[field] for field in UNCHANGED_BLOCK_FIELDS),
              "HISTORICAL_EMPHASIS_CHANGED_MORE_THAN_THE_EMPHASIS_FIELDS")
    body = {key: value for key, value in document.items() if key != "text_document_id"}
    body["blocks"] = blocks
    return {**body, "text_document_id": content_hash(value=body)}


def _heading_only(block):
    prefix = block["leading_emphasis"]
    return prefix is not None and not block["linked"] and prefix["text"] == block["text"]


def split_heading_requires_multispan(*, blocks, section):
    """Recognize the known page-split layout without inventing one raw span."""
    if not section or section.get("status") != "LOCATED" or len(section["candidates"]) != 1:
        return False
    scope = section["candidates"][0]
    start, end = scope["start_block"], scope["end_block_exclusive"]
    for index in range(start, max(start, end - 3)):
        block = blocks[index]
        page, contents, continuation = blocks[index + 1:index + 4]
        if (_heading_only(block) and not _SENTENCE_END.search(block["text"])
                and _PAGE_NUMBER.fullmatch(page["text"].strip())
                and contents["linked"]
                and contents["text"].strip().casefold() == _CONTENTS_LINK
                and _heading_only(continuation)
                and continuation["text"][:1].islower()):
            return True
    return False
