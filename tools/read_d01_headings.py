"""Read D01's risk-factor headings off a filing's own bytes, apart from the route.

The route locates Item 1A with text_coverage, takes each block's leading
emphasis from a successor parser that also admits underline, and hands the
blocks to the frozen heading selector. A reading that asked those modules what
the headings are would be checking the route against itself, so none of them
is imported. This parses the saved HTML with its own small reader: blocks at
block-level tags, runs carrying the bold, underline and italic their own
styles and tags give them, Item 1A found by its own heading and ended by the
next item's.

Three directions, as for every D01 reading:

1. every heading the route published is a heading-marked run in Item 1A, in
   the filing's order - compared line for line, not as a set;
2. every heading-marked run in Item 1A is among the published lines, so a
   heading the route dropped shows up here;
3. every other visually marked block the filing has in Item 1A - italic, which
   this corpus uses for other things - carries a recorded judgement, and a
   block with none fails the reading.

What makes a run heading-marked - bold or underline, not in a link, not page
furniture - is the reading's own statement of the mark this filing uses for
its headings, measured from its bytes: Marriott sets its two top-level
categories in bold and the rest in underline inside the same wrapper and face.
The judgement that each line is a heading in the business sense is recorded
per filing below; it is the part a program cannot supply.

Usage:
    python3 tools/read_d01_headings.py --runs-root <root> --closure sha256:<closure> \
        --company marriott_international --period-end 2025-12-31 [...]
"""
import argparse
import collections
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import accession_of_document  # noqa: E402
from bind_acceptance_readings import identity_for  # noqa: E402
from vnext.historical_coverage import select_receipt  # noqa: E402
from vnext.historical_run_receipts import collect_run_receipts, index_receipts  # noqa: E402

BLOCK_TAGS = {"div", "p", "tr", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"}
VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "col", "wbr"}
ITEM_1A = re.compile(r"^\s*item\s*1a\b", re.I)
NEXT_ITEM = re.compile(r"^\s*item\s*(?:1b|1c|2)\b", re.I)
FURNITURE = re.compile(r"^(?:table of contents|\d+|[ivx]+-\d+|.*form 10-k.*)$", re.I)
WEIGHT = re.compile(r"font-weight\s*:\s*(bold|bolder|\d+)", re.I)


def _style(style, inherited):
    bold, underline, italic = inherited
    style = style or ""
    weight = WEIGHT.search(style)
    if weight:
        value = weight.group(1).lower()
        bold = value in ("bold", "bolder") or (value.isdigit() and int(value) >= 600)
    decoration = re.search(r"text-decoration(?:-line)?\s*:\s*([^;]+)", style, re.I)
    if decoration:
        underline = "underline" in decoration.group(1).lower()
    font_style = re.search(r"font-style\s*:\s*([^;]+)", style, re.I)
    if font_style:
        italic = "italic" in font_style.group(1).lower()
    return bold, underline, italic


class _Blocks(HTMLParser):
    """Blocks of styled runs, in document order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.current = [], []
        self.stack = [(False, False, False, False)]

    def _flush(self):
        if any(text.strip() for text, *_ in self.current):
            self.blocks.append(self.current)
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self._flush()
        if tag in VOID_TAGS:
            return
        bold, underline, italic, linked = self.stack[-1]
        attributes = dict(attrs)
        if tag in ("b", "strong"):
            bold = True
        if tag == "u":
            underline = True
        if tag in ("i", "em"):
            italic = True
        if tag == "a" and attributes.get("href"):
            linked = True
        bold, underline, italic = _style(attributes.get("style"), (bold, underline, italic))
        self.stack.append((bold, underline, italic, linked))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if len(self.stack) > 1:
            self.stack.pop()
        if tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        bold, underline, italic, linked = self.stack[-1]
        self.current.append((data, bold, underline, italic, linked))

    def close(self):
        super().close()
        self._flush()


def _text(runs):
    return re.sub(r"\s+", " ", "".join(text for text, *_ in runs)).strip()


def _resumes_after_a_gap(runs, *, marks):
    """Whether emphasis stops for a short unmarked gap and then resumes.

    Two or fewer characters, such as the periods in "U.S." left unbolded, then
    marked text again. A prefix that stops there is cut inside what the filing
    sets as one heading; a longer gap is the ordinary end of a lead-in. This is
    a flag for the reader's judgement, not a rule the reading applies.
    """
    state, gap = "BEFORE", ""
    for text, bold, underline, italic, linked in runs:
        carried = {"bold": bold, "underline": underline, "italic": italic}
        marked = any(carried[mark] for mark in marks) and not linked
        if not text.strip():
            continue
        if state == "BEFORE":
            state = "IN" if marked else "OUT"
            if state == "OUT":
                return False
        elif state == "IN" and not marked:
            state, gap = "GAP", text
        elif state == "GAP":
            if marked:
                return len(gap.strip()) <= 2
            gap += text
            if len(gap.strip()) > 2:
                return False
    return False


def _marked_prefix(runs, *, marks):
    """The block's leading runs that carry one of ``marks``, joined.

    Whitespace-only runs neither start nor end the prefix. Returns None when
    the block's first visible run does not carry a mark or sits in a link.
    """
    prefix = []
    for text, bold, underline, italic, linked in runs:
        if not text.strip():
            if prefix:
                prefix.append(text)
            continue
        carried = {"bold": bold, "underline": underline, "italic": italic}
        if linked or not any(carried[mark] for mark in marks):
            break
        prefix.append(text)
    joined = re.sub(r"\s+", " ", "".join(prefix)).strip()
    return joined or None


def _marked_across_short_gaps(runs, *, marks):
    """The marked prefix, continued over unmarked gaps of two characters or fewer.

    Computed only for a line _resumes_after_a_gap flags, so that the recorded
    judgement has the filing's own text for both readings to choose between.
    The reading applies no rule here: which of the two is the heading is the
    judgement, and a flagged line with none fails the reading.
    """
    kept, gap = [], []
    for text, bold, underline, italic, linked in runs:
        carried = {"bold": bold, "underline": underline, "italic": italic}
        marked = any(carried[mark] for mark in marks) and not linked
        if not text.strip():
            if kept:
                (gap if gap else kept).append(text)
            continue
        if marked:
            kept.extend(gap)
            gap = []
            kept.append(text)
        elif not kept:
            break
        else:
            gap.append(text)
            if len("".join(gap).strip()) > 2:
                break
    joined = re.sub(r"\s+", " ", "".join(kept)).strip()
    return joined or None


SHORT_GAP_DECISIONS = ("ONE_HEADING_ACROSS_THE_GAP", "HEADING_ENDS_AT_THE_GAP")


def judged_lines(*, headings, shapes, short_gap_lines):
    """The heading lines after each flagged line's recorded judgement.

    ``short_gap_lines`` maps a flagged line's prefix to one of
    SHORT_GAP_DECISIONS. Returns ``(lines, unjudged, not_found)``: a flagged
    line with no judgement, and a judgement naming a line the filing does not
    flag, each fail the reading - the second because a judgement about a line
    this filing does not have describes some other filing.
    """
    lines, flagged = [], set()
    for text, shape in zip(headings, shapes):
        if shape["emphasis_resumes_after_a_short_gap"]:
            flagged.add(text)
            if short_gap_lines.get(text) == "ONE_HEADING_ACROSS_THE_GAP":
                text = shape["across_short_gaps"]
        lines.append(text)
    unjudged = sorted(line for line in flagged if short_gap_lines.get(line)
                      not in SHORT_GAP_DECISIONS)
    return lines, unjudged, sorted(set(short_gap_lines) - flagged)


def as_published(headings):
    """The heading lines in the shape the route publishes them.

    risk_signals.risk_factor_headings lists identical heading text once, at its
    first occurrence, and keeps the other occurrences as locators. A
    Southwest-style summary names each category before the detailed section,
    and the detailed category is not a second heading.
    """
    return list(dict.fromkeys(headings))


def read_item_1a(*, raw_bytes):
    """Item 1A's blocks, located by its own heading and the next item's."""
    parser = _Blocks()
    parser.feed(raw_bytes.decode("utf-8", "replace"))
    parser.close()
    blocks = parser.blocks
    starts = [index for index, runs in enumerate(blocks)
              if ITEM_1A.match(_text(runs)) and not any(r[4] for r in runs)
              and _marked_prefix(runs, marks=("bold", "underline"))]
    if not starts:
        raise SystemExit("ITEM_1A_HEADING_NOT_FOUND")
    spans = []
    for start in starts:
        ends = [index for index in range(start + 1, len(blocks))
                if NEXT_ITEM.match(_text(blocks[index]))
                and not any(r[4] for r in blocks[index])]
        if ends:
            spans.append((ends[0] - start, start, ends[0]))
    if not spans:
        raise SystemExit("NEXT_ITEM_HEADING_NOT_FOUND")
    # A table of contents names every item too, and some tables of contents
    # set their item labels in bold without a link - measured on Salesforce,
    # where the first "Item 1A." is a contents row and the item it starts is
    # three blocks long. The item itself is the longest span.
    _, start, end = max(spans)
    first = start + 1
    # The item's own title, when the filing sets "Item 1A." and "Risk
    # Factors." as two blocks - measured on Paramount. It titles the item; it
    # is not a heading inside it.
    if first < end and re.fullmatch(r"risk factors\.?", _text(blocks[first]), re.I):
        first += 1
    return blocks[first:end]


def headings_and_other_marks(*, raw_bytes, registrant_names=()):
    """Heading-marked lines, their shapes, and other visually marked blocks.

    Returns ``(headings, shapes, others)``. A shape says which mark carried the
    line and whether the block is the heading alone or a heading leading into
    its body - which is what a reader needs to judge a line as a category or a
    risk factor, and what the judgement below is recorded against.
    """
    names = {re.sub(r"\W", "", name).casefold() for name in registrant_names}
    headings, shapes, others = [], [], []
    for position, runs in enumerate(read_item_1a(raw_bytes=raw_bytes)):
        text = _text(runs)
        if not text or FURNITURE.match(text):
            continue
        heading = _marked_prefix(runs, marks=("bold", "underline"))
        # A marked prefix with no letter - a bold bullet, a number - labels
        # nothing. Measured on Salesforce, whose summary bullets are bold.
        if heading and not re.search(r"[A-Za-z]", heading):
            heading = None
        if heading and re.sub(r"\W", "", heading).casefold() not in names:
            first = next(run for run in runs if run[0].strip())
            body = len(text) - len(heading)
            headings.append(heading)
            resumes = _resumes_after_a_gap(runs, marks=("bold", "underline"))
            shapes.append({"mark": "BOLD" if first[1] else "UNDERLINE",
                           "shape": "STANDALONE" if body <= 1 else "LEADS_INTO_ITS_BODY",
                           "body_chars": max(body, 0),
                           "emphasis_resumes_after_a_short_gap": resumes,
                           **({"across_short_gaps": _marked_across_short_gaps(
                               runs, marks=("bold", "underline"))} if resumes else {})})
            continue
        italic = _marked_prefix(runs, marks=("italic",))
        if italic:
            others.append({"block_in_item_1a": position, "text": text[:160]})
    return headings, shapes, others


def read_position(*, index, closure, company_id, period_end, judgements):
    """One position: select the result, read its filing, compare both ways."""
    key = (company_id, "D01", period_end)
    selection = select_receipt(found=index.get(key, []), closure=closure)
    if selection["result"] is None:
        raise SystemExit("NO_RESULT:" + "/".join(key) + ":" + str(selection["ambiguity"]))
    result, receipt = selection["result"], selection["receipt"]
    run_dir = Path(receipt["_runs_root"]) / receipt["run_directory_name"]
    references = [json.loads(line) for line in
                  (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
                  if line.strip()]
    target = [r for r in references if r.get("record_type") == "SOURCE_REFERENCE"
              and r.get("source_role") == "target_primary"]
    blobs = {r["raw_asset_id"]: r for r in references if r.get("record_type") == "RAW_BLOB"}
    if len(target) != 1:
        raise SystemExit("TARGET_DOCUMENT_NOT_UNIQUE:" + "/".join(key))
    storage = blobs[target[0]["raw_asset_id"]]["storage_uri"]
    raw = (REPO / storage).read_bytes()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != target[0]["raw_asset_id"]:
        raise SystemExit("SAVED_DOCUMENT_BYTES_CHANGED:" + storage)
    accession, cik = accession_of_document(repo_root=REPO, document=storage)
    # The cover's own statement of the period. The first "fiscal year ended"
    # in a filing is often a reference to an earlier report, so the cover's
    # "For the fiscal year ended" is asked for by that phrase; tag stripping
    # can leave a space before the comma, which the pattern allows.
    flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&#160;|&nbsp;", " ",
                                      raw.decode("utf-8", "replace")))
    cover = re.search(r"for the fiscal year ended ([A-Za-z]+) (\d{1,2}) ?, ?(\d{4})", flat, re.I)
    cover_end = None
    if cover:
        import datetime
        cover_end = datetime.datetime.strptime(
            cover.group(1).title() + " " + cover.group(2) + " " + cover.group(3),
            "%B %d %Y").date().isoformat()
    # The registrant's name as the filing tags it, so a page header carrying
    # the name is not taken as a heading. Read from the filing, not supplied.
    registrant_names = sorted(set(re.findall(
        r'name="dei:EntityRegistrantName"[^>]*>(?:<[^>]+>)*([^<]+)<',
        raw.decode("utf-8", "replace"))))
    headings, shapes, others = headings_and_other_marks(
        raw_bytes=raw, registrant_names=registrant_names)
    short_gap_lines = {entry["line"]: entry["decision"]
                       for entry in judgements.get("short_gap_lines", ())}
    lines, gap_unjudged, gap_not_found = judged_lines(
        headings=headings, shapes=shapes, short_gap_lines=short_gap_lines)
    published = str(result["value"]).split("\n")
    distinct = as_published(lines)
    judged = {entry["block_in_item_1a"]: entry["judgement"]
              for entry in judgements.get("other_marks", ())}
    found = {entry["block_in_item_1a"] for entry in others}
    position = {
        "reading": "D01_HEADINGS_READ_FROM_THE_FILING_BYTES", "company_id": company_id,
        "period_end": period_end, "accession": accession, "registrant_cik": cik,
        "document": storage, "fiscal_year_end_on_the_cover": cover_end,
        "registrant_names_tagged_in_the_filing": registrant_names,
        "headings_read": distinct,
        "repeated_heading_occurrences_grouped": len(lines) - len(distinct),
        "heading_shapes": dict(collections.Counter(
            shape["mark"] + ":" + shape["shape"] for shape in shapes)),
        "heading_lines": [{"text": text, **shape} for text, shape in zip(headings, shapes)],
        "lines_where_emphasis_resumes_after_a_short_gap": [
            text for text, shape in zip(headings, shapes)
            if shape["emphasis_resumes_after_a_short_gap"]],
        # Which reading of each flagged line is the heading: recorded, not
        # decided here. The row carries the decisions so the reading can be
        # reproduced from the filing and this row alone.
        "short_gap_judgements": short_gap_lines,
        "short_gap_lines_with_no_judgement": gap_unjudged,
        "short_gap_judgements_not_found_in_the_filing": gap_not_found,
        # The part a program cannot supply: whether each line is a heading in
        # the approved definition's sense. Recorded per filing; the reading
        # fails without it, and fails when it names a line as wrong.
        "business_judgement": judgements.get("every_line"),
        "lines_judged_wrong": judgements.get("lines_judged_wrong", []),
        "published_lines": len(published),
        "published_equals_read_in_order": published == distinct,
        "published_not_read": [line for line in published if line not in distinct],
        "read_not_published": [line for line in distinct if line not in published],
        "other_marked_blocks": others,
        "other_marked_blocks_with_no_judgement": sorted(found - set(judged)),
        "recorded_judgements_not_found_in_the_filing": sorted(set(judged) - found),
        "value_sha256": "sha256:" + hashlib.sha256(
            str(result["value"]).encode("utf-8")).hexdigest()}
    position["verdict"] = ("MATCH" if position["published_equals_read_in_order"]
                           and cover_end == period_end
                           and position["business_judgement"]
                           and not position["lines_judged_wrong"]
                           and not position["other_marked_blocks_with_no_judgement"]
                           and not position["recorded_judgements_not_found_in_the_filing"]
                           and not gap_unjudged and not gap_not_found
                           else "DIFFERS")
    identity, refusal = identity_for(
        position={"company_id": company_id, "metric_id": "D01", "period_end": period_end,
                  "published": position["value_sha256"], "reading_filings": [accession],
                  "reading_window": None, "filings_are_the_whole_set": False},
        index=index, closure=closure)
    if refusal is not None:
        raise SystemExit("IDENTITY_NOT_RECORDED:" + refusal)
    identity["established_by"] = "RECORDED_AT_READING_TIME"
    position["checked_identity"] = identity
    return position


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    parser.add_argument("--position", required=True, action="append",
                        help="<company_id>:<period_end>")
    parser.add_argument("--out", required=True)
    parser.add_argument("--judgements", type=Path)
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        for receipt in collect_run_receipts(runs_root=root)["receipts"]:
            receipts.append({**receipt, "_runs_root": str(root)})
    index = index_receipts(receipts=receipts)
    judgements = (json.loads(arguments.judgements.read_text(encoding="utf-8"))
                  if arguments.judgements else {})
    positions = {}
    for requested in arguments.position:
        company_id, period_end = requested.split(":")
        label = company_id.split("_")[0] + "-" + period_end[:4]
        positions[label] = read_position(index=index, closure=arguments.closure,
                                         company_id=company_id, period_end=period_end,
                                         judgements=judgements.get(label, {}))
        row = positions[label]
        print(label, row["verdict"], "read", len(row["headings_read"]),
              "published", row["published_lines"],
              "unjudged", row["other_marked_blocks_with_no_judgement"], flush=True)
    (REPO / arguments.out).write_text(json.dumps(
        {"record_type": "ISSUE_47_D01_HEADINGS_READ_FROM_BYTES",
         "requirement_closure_hash": arguments.closure,
         "judgements": str(arguments.judgements) if arguments.judgements else None,
         "per_position": positions, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
