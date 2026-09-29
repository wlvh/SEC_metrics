"""Does any text a reader cannot see fall inside an item body the E01 route reads?

The historical E01 route reads a candidate item's body from the frozen
``deterministic_router._visible_text`` view, which keeps every text node of the
primary document - including those inside <style>, <script>, <head>,
ix:hidden and elements styled display:none. Issue #28 found the same risk in
its opt-in 8.01 source component (base commit d1caf720) and now excludes
hidden DOM and refuses text whose visibility cannot be established.

This rebuilds the frozen view piece by piece with a parser that also records,
for each text node, whether an enclosing element hides it and whether an
enclosing inline style makes its visibility uncertain; checks that the rebuilt
text equals the frozen view exactly; and, for every candidate item (1.01, 2.01,
8.01) of every saved 8-K, reports the pieces inside the route's item span that
are hidden or uncertain. Zero network calls.
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext.deterministic_router import _hdr_item_codes, _visible_text  # noqa: E402
from vnext.historical_event_items import EventItemTextError, item_text  # noqa: E402

CANDIDATES = ("1.01", "2.01", "8.01")
NONDISPLAY = {"head", "script", "style", "template", "noscript", "svg", "ix:hidden", "title"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr"}
HIDING = re.compile(r"(?:^|;)(?:display:none|visibility:hidden|content-visibility:hidden)(?:;|$|!)")


def _style(attributes):
    return re.sub(r"\s+", "", attributes.get("style") or "").lower()


NUMBER = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))(px|pt|em|rem|%|in|cm|mm|pc|ex|ch|vw|vh)?$")
BROAD = re.compile(r"(?:^|;)(?:opacity|color|background|background-color|clip|clip-path|filter|"
                   r"position|transform|z-index):|(?:^|;)font-size:0(?:[^0-9.]|$)")


def _uncertain(style):
    """Inline declarations whose value alone makes text invisible (the rule the route adopts).

    Written here independently of the route's module, so the census taken
    before the change and the check after it are two readings, not one.
    """
    found = []
    for declaration in style.split(";"):
        name, _, value = declaration.partition(":")
        value = value.replace("!important", "")
        match = NUMBER.match(value)
        number = float(match.group(1)) * (0.01 if match.group(2) == "%" else 1) if match else None
        if name == "opacity" and (number is None or number < 0.1):
            found.append(name + ":" + value)
        elif name == "font-size" and number == 0:
            found.append(name + ":" + value)
        elif name == "color" and (value == "transparent" or re.fullmatch(r"rgba\([^)]*,0*\.?0*\)", value)):
            found.append(name + ":" + value)
        elif name in ("text-indent", "left", "top", "margin-left", "margin-top") and \
                number is not None and number <= -999:
            found.append(name + ":" + value)
    return found


def _hanging(style):
    """A negative first-line indent short of the page: layout, not hiding."""
    for declaration in style.split(";"):
        name, _, value = declaration.partition(":")
        match = NUMBER.match(value)
        if name == "text-indent" and match and -999 < float(match.group(1)) < 0:
            return name + ":" + value
    return None


class Annotated(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.pieces = []
        self.stylesheet = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        style = _style(attributes)
        if tag == "style" or (tag == "link" and "stylesheet" in (attributes.get("rel") or "").lower()):
            self.stylesheet = True
        parent_hidden = bool(self.stack and self.stack[-1]["hidden"])
        hidden_by = None
        if parent_hidden:
            hidden_by = self.stack[-1]["hidden_by"]
        elif tag in NONDISPLAY:
            hidden_by = "tag:" + tag
        elif "hidden" in attributes:
            hidden_by = "attribute:hidden"
        elif (attributes.get("aria-hidden") or "").lower() == "true":
            hidden_by = "aria-hidden"
        elif HIDING.search(style):
            hidden_by = "style:" + HIDING.search(style).group(0).strip(";")
        uncertain = list(self.stack[-1]["uncertain"]) if self.stack else []
        uncertain += _uncertain(style)
        hanging = (self.stack[-1]["hanging"] if self.stack else None) or _hanging(style)
        broad = (bool(self.stack[-1]["broad"]) if self.stack else False) or bool(BROAD.search(style))
        if tag not in VOID:
            self.stack.append({"tag": tag, "hidden": hidden_by is not None, "hidden_by": hidden_by,
                               "uncertain": uncertain, "hanging": hanging, "broad": broad})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        text = data.strip()
        if text:
            top = self.stack[-1] if self.stack else {"hidden_by": None, "uncertain": [],
                                                     "hanging": None, "broad": False}
            self.pieces.append({"text": " ".join(text.split()), "hidden_by": top["hidden_by"],
                                "uncertain": top["uncertain"], "hanging": top["hanging"],
                                "broad": top["broad"]})


def annotate(raw):
    parser = Annotated()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    offset = 0
    for piece in parser.pieces:
        piece["start"] = offset
        piece["end"] = offset + len(piece["text"])
        offset = piece["end"] + 1
    rebuilt = " ".join(piece["text"] for piece in parser.pieces)
    return parser, rebuilt


def main():
    rows, mismatched = [], []
    for folder in sorted((REPO / "evidence/accession_materials").iterdir()):
        headers = sorted(folder.glob("*.hdr.sgml"))
        if not headers:
            continue
        header = headers[0].read_bytes().decode("utf-8", "replace")
        form = re.search(r"<TYPE>\s*([^\r\n]+)", header)
        if form is None or form.group(1).strip() not in ("8-K", "8-K/A"):
            continue
        codes = [code for code in _hdr_item_codes(raw_bytes=headers[0].read_bytes())
                 if code in CANDIDATES]
        if not codes:
            continue
        primaries = [path for path in folder.iterdir() if path.suffix in (".htm", ".html")]
        if len(primaries) != 1:
            rows.append({"folder": folder.name, "status": "PRIMARY_NOT_UNIQUE",
                         "documents": sorted(p.name for p in primaries)})
            continue
        raw = primaries[0].read_bytes()
        parser, rebuilt = annotate(raw)
        frozen = _visible_text(raw_bytes=raw)
        if rebuilt != frozen:
            mismatched.append(folder.name)
            continue
        for code in codes:
            try:
                item = item_text(raw_bytes=raw, item_code=code)
            except EventItemTextError as error:
                rows.append({"folder": folder.name, "item_code": code, "status": "NOT_LOCATED",
                             "reason": str(error)})
                continue
            inside = [p for p in parser.pieces if p["end"] > item["start"] and p["start"] < item["end"]]
            hidden = [p for p in inside if p["hidden_by"]]
            uncertain = [p for p in inside if not p["hidden_by"] and p["uncertain"]]
            rows.append({
                "folder": folder.name, "document": primaries[0].name, "item_code": code,
                "text_sha256": item["text_sha256"], "end_marker": item["end_marker"],
                "span_characters": item["end"] - item["start"], "pieces_in_span": len(inside),
                "hidden_pieces_in_span": len(hidden),
                "hidden_characters_in_span": sum(len(p["text"]) for p in hidden),
                "hidden_samples": [{"by": p["hidden_by"], "text": p["text"][:120]} for p in hidden[:5]],
                "uncertain_pieces_in_span": len(uncertain),
                "uncertain_samples": [{"by": p["uncertain"][:3], "text": p["text"][:120]}
                                      for p in uncertain[:5]],
                "hanging_indent_pieces_in_span": sum(1 for p in inside if p["hanging"]),
                "broad_rule_would_refuse": any(p["broad"] for p in inside),
                "document_has_stylesheet": parser.stylesheet,
                "hidden_pieces_in_document": sum(1 for p in parser.pieces if p["hidden_by"]),
            })
    summary = {
        "documents_rebuilt_equal_to_the_frozen_view": len({r["folder"] for r in rows
                                                            if "span_characters" in r}),
        "documents_whose_rebuild_differs": mismatched,
        "candidate_items": sum(1 for r in rows if "span_characters" in r),
        "items_with_hidden_text_in_span": sum(1 for r in rows if r.get("hidden_pieces_in_span")),
        "items_with_uncertain_text_in_span": sum(1 for r in rows
                                                 if r.get("uncertain_pieces_in_span")),
        "items_not_located": sum(1 for r in rows if r.get("status") == "NOT_LOCATED"),
        "items_with_a_hanging_indent_in_span": sum(1 for r in rows
                                                   if r.get("hanging_indent_pieces_in_span")),
        "items_a_broad_inline_style_rule_would_refuse": sum(1 for r in rows
                                                            if r.get("broad_rule_would_refuse")),
        "documents_with_a_stylesheet": len({r["folder"] for r in rows
                                            if r.get("document_has_stylesheet")}),
        "documents_with_hidden_text_anywhere": len({r["folder"] for r in rows
                                                    if r.get("hidden_pieces_in_document")}),
    }
    out = {"record_type": "ISSUE_47_E01_HIDDEN_TEXT_CENSUS", "summary": summary, "rows": rows,
           "calls": [0, 0, 0]}
    print(json.dumps(summary, indent=1))
    Path(__file__).with_name("hidden-text-census.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
