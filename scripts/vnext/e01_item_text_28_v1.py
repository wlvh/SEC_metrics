"""Pinned #28 E01 item-text reader from #47 source commit 488a6173.

This version only locates source text; it neither confirms M&A nor counts items.
The pure parsing algorithm is copied from historical_event_items.py before
its historical route/registration functions, with an independent #28 path.
"""
import re
from html.parser import HTMLParser

from .canonical import sha256_bytes
from .deterministic_router import _visible_text

PEER_SOURCE_SHA = '488a61734978adaa57e82ec0654e75a0af284cfb'
RULE = 'ITEM_TEXT_FROM_ITS_HEADING_TO_THE_NEXT_ITEM_HEADING_OR_THE_SIGNATURES'
TEXT_VIEW = 'deterministic_router._visible_text'

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
# Form 8-K's own captions for the items a successor route reads as candidates,
# and for the items filers most often head beside them. An item whose text is
# nothing but its caption, followed at once by another item's heading, is one
# whose content the filer wrote once under the headings together - Ford heads a
# credit-agreement amendment "Item 1.01 ... Item 2.03 ..." and writes it under
# 2.03 - so it shares the body that follows. The captions are the form's, not
# any filer's, and nothing is inferred from a caption that is not on this list.
_CAPTIONS = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.03": ("Creation of a Direct Financial Obligation or an Obligation under an "
             "Off-Balance Sheet Arrangement of a Registrant"),
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}
_LETTERS = re.compile(r"[^a-z]+")
_EXHIBIT = re.compile(r"\bExhibits?\s+\d+(?:\.\d+)?", re.I)
_CONTEXT = 240


# Elements whose text is never displayed, and the inline declarations that hide
# an element or make its text invisible. A value that cannot be read as a
# number is treated as hiding for the properties that hide by their value: an
# item is refused rather than read when its visibility cannot be established.
_NONDISPLAY = frozenset(("head", "title", "script", "style", "template", "noscript", "svg",
                         "ix:hidden"))
_VOID = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
                   "param", "source", "track", "wbr"))
_NUMBER = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))(px|pt|em|rem|%|in|cm|mm|pc|ex|ch|vw|vh)?$")
_OFF_THE_PAGE = 999


def _number(value):
    match = _NUMBER.match(value)
    return None if match is None else (float(match.group(1)), match.group(2) or "")


def _hidden_by_style(style):
    """The inline declaration that keeps an element's text from being seen, or None."""
    for declaration in style.split(";"):
        name, _, value = declaration.partition(":")
        value = value.replace("!important", "")
        if not name or not value:
            continue
        if ((name == "display" and value == "none")
                or (name == "visibility" and value in ("hidden", "collapse"))
                or (name == "content-visibility" and value == "hidden")
                or (name == "color" and (value == "transparent"
                                         or re.fullmatch(r"rgba\([^)]*,0*\.?0*\)", value)))):
            return name + ":" + value
        number = _number(value)
        if name == "opacity" and (number is None or number[0] * (0.01 if number[1] == "%" else 1)
                                  < 0.1):
            return name + ":" + value
        if name == "font-size" and number is not None and number[0] == 0:
            return name + ":" + value
        # An offset this large moves the text off the page whichever way it
        # points: left or up past the page's start, or right or down past where
        # a reader looks. #28's review of its own reader found right/bottom and
        # large positive offsets admitted (7fc74694); this reader had them too.
        if (name in ("text-indent", "left", "right", "top", "bottom", "margin-left", "margin-top")
                and number is not None and abs(number[0]) >= _OFF_THE_PAGE):
            return name + ":" + value
    return None


class _Visibility(HTMLParser):
    """The frozen view's text nodes, each with what hides it and whether a link holds it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.stack, self.links, self.nodes = [], [], [], []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        hidden = self.stack[-1] if self.stack else None
        linked = (self.links[-1] if self.links else False) or (tag == "a" and "href" in attributes)
        if hidden is None:
            style = re.sub(r"\s+", "", attributes.get("style") or "").lower()
            if tag in _NONDISPLAY:
                hidden = "element:" + tag
            elif "hidden" in attributes:
                hidden = "attribute:hidden"
            elif (attributes.get("aria-hidden") or "").lower() == "true":
                hidden = "attribute:aria-hidden"
            else:
                hidden = _hidden_by_style(style)
                hidden = None if hidden is None else "style:" + hidden
        if tag not in _VOID:
            self.tags.append(tag)
            self.stack.append(hidden)
            self.links.append(linked)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.tags) - 1, -1, -1):
            if self.tags[index] == tag:
                del self.tags[index:]
                del self.stack[index:]
                del self.links[index:]
                return

    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.nodes.append((text, self.stack[-1] if self.stack else None,
                               self.links[-1] if self.links else False))


def _text_nodes(*, raw_bytes, text):
    """``(start, end, hidden, linked)`` for each node of the frozen view, rebuilt and checked."""
    parser = _Visibility()
    parser.feed(raw_bytes.decode("utf-8", errors="replace"))
    parser.close()
    _need(" ".join(node for node, _, _ in parser.nodes) == text, "EVENT_ITEM_TEXT_VIEW_NOT_REBUILT")
    spans, offset = [], 0
    for node, hidden, linked in parser.nodes:
        spans.append((offset, offset + len(node), hidden, linked))
        offset += len(node) + 1
    return spans


def _hidden_in_span(*, nodes, start, end):
    """What hides a node inside [start, end) of the frozen view, or None."""
    for node_start, node_end, hidden, _ in nodes:
        if hidden is not None and node_start < end and node_end > start:
            return hidden
    return None


def _linked_in_span(*, nodes, start, end):
    """Whether a node inside [start, end) of the frozen view sits inside a link."""
    return any(linked and node_start < end and node_end > start
               for node_start, node_end, _, linked in nodes)


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
    # Caption-only items share the body of the headings that follow them, as
    # far as each one in turn is caption-only too.
    shared, body_from = [], own[0][-1][1]
    following = [heading for heading in headings if heading[0] >= body_from]
    while (following and following[0][2] != item_code
           and _caption_only(text[body_from:following[0][0]], code=item_code if not shared
                             else shared[-1])):
        shared.append(following[0][2])
        body_from = following[0][1]
        following = following[1:]
        later = [heading[0] for heading in following if heading[2] != item_code]
    signatures = _SIGNATURES.search(text, heading_end if not shared else body_from)
    if later and (signatures is None or later[0] < signatures.start()):
        end, marker = later[0], "NEXT_ITEM_HEADING"
    elif signatures is not None:
        end, marker = signatures.start(), "SIGNATURES"
    else:
        end, marker = len(text), "END_OF_DOCUMENT"
    if marker == "NEXT_ITEM_HEADING":
        end_code = next(code for position, _, code in headings if position == end)
        _need(sum(1 for position, _, code in headings if code == end_code and position > start) == 1,
              "EVENT_ITEM_END_HEADING_NOT_UNIQUE:" + item_code + ":" + end_code)
    elif marker == "SIGNATURES":
        _need(len(_SIGNATURES.findall(text, start)) == 1,
              "EVENT_ITEM_END_SIGNATURES_NOT_UNIQUE:" + item_code)
    nodes = _text_nodes(raw_bytes=raw_bytes, text=text)
    # A heading inside a link is a reference to the item - a contents entry -
    # not the item's own heading. The frozen view does not know links, so an
    # item whose only heading is a link would read the contents as its text.
    _need(not _linked_in_span(nodes=nodes, start=start, end=heading_end),
          "EVENT_ITEM_HEADING_IS_A_LINK:" + item_code)
    hidden = _hidden_in_span(nodes=nodes, start=start, end=end)
    _need(hidden is None, "EVENT_ITEM_TEXT_A_READER_CANNOT_SEE:" + item_code + ":" + str(hidden))
    body = text[start:end]
    return {"item_code": item_code, "text_view": TEXT_VIEW, "rule": RULE,
            "start": start, "end": end, "end_marker": marker,
            "heading": text[start:heading_end].strip(), "text": body,
            "text_sha256": "sha256:" + sha256_bytes(content=body.encode("utf-8")),
            "shares_the_body_of": shared}


def _caption_only(gap, *, code):
    """True where ``gap`` - what follows an item's heading - is only that item's own caption."""
    caption = _CAPTIONS.get(code)
    return caption is not None and _LETTERS.sub("", gap.lower()) == _LETTERS.sub("", caption.lower())


