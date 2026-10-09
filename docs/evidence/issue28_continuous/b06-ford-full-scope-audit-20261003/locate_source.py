#!/usr/bin/env python3
"""Read-only byte-bound Ford 10-K page locator; standard library only.

Pages are 1-based HTML segments separated by the original page-break HRs.
Printed report page numbers are reported separately; source bytes are unchanged.
"""
import argparse
import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HTML = ROOT / "evidence/request_attempts/3b/3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9/f-20251231.htm"
EXPECTED = "3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9"
BREAK = re.compile(rb"<hr\b[^>]*page-break-after:always[^>]*>", re.I)


class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = []

    def handle_starttag(self, tag, attrs):
        if tag in {"head", "script", "style", "ix:header", "ix:hidden"}:
            self.skip.append(tag)
        if self.skip:
            return
        if tag in {"div", "p", "tr", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag in {"div", "p", "tr"}:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        lines = [re.sub(r"[\t \u00a0]+", " ", x).strip(" |") for x in "".join(self.parts).splitlines()]
        return "\n".join(x for x in lines if x)


def pages():
    raw = HTML.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != EXPECTED:
        raise SystemExit(f"Source SHA256 changed: {actual}")
    cursor = 0
    bounds = []
    for match in BREAK.finditer(raw):
        bounds.append((cursor, match.start()))
        cursor = match.end()
    bounds.append((cursor, len(raw)))
    for ordinal, (start, end) in enumerate(bounds, 1):
        parser = Visible()
        parser.feed(raw[start:end].decode("utf-8"))
        text = parser.text()
        lines = text.splitlines()
        printed = lines[-1] if lines and re.fullmatch(r"\d+", lines[-1]) else "unidentified"
        yield ordinal, start, end, printed, text


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pages", help="Inclusive HTML page ordinals, e.g. 90:100 or 105")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--find", help="Regex search, with a bounded local excerpt per matching page")
    args = ap.parse_args()
    selected = None
    if args.pages:
        a, _, b = args.pages.partition(":")
        selected = (int(a), int(b or a))
    for ordinal, start, end, printed, text in pages():
        if selected and not selected[0] <= ordinal <= selected[1]:
            continue
        if args.find:
            match = re.search(args.find, text, re.I)
            if not match:
                continue
            text = text[max(0, match.start() - 250):match.end() + 600]
        label = f"HTML_PAGE {ordinal}; PRINTED_PAGE {printed}; RAW_BYTES [{start},{end})"
        if args.index:
            lines = text.splitlines()
            titles = [x for x in lines if re.search(r"^(?:NOTE \d|CONSOLIDATED |ITEM \d|Liquidity|Capital Resources|Financial Condition)", x, re.I)]
            print(label, "; HEAD", " / ".join(lines[:2])[:140], "; TITLES", " / ".join(titles[:8]))
        else:
            print(label)
            print(text)


if __name__ == "__main__":
    main()
