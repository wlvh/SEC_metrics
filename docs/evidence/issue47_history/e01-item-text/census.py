"""Every saved 8.01, read the way the historical E01 route now reads it.

For each saved 8-K whose header lists item 8.01 this records where the route's
reading (``historical_event_items.item_text``) finds the item, where it stops,
and every declared alias in its own text; and beside it the judgement a person
made reading the same item in full (e01-keyword-branch/eight-o-one-judgements.json
for the seven value windows, more-eight-o-one-judgements.json for the rest).

It then counts, over the same forty items, what each candidate meaning of the
confirmation would admit, so the decision is made against the corpus rather
than against the one example that prompted it:

* ``LITERAL_ALIAS_IN_THE_ITEM`` - the approved substring rule on the item's own text;
* ``CONTENT_REPORTS_A_TRANSACTION`` - the recorded judgement, keyword or not;
* ``NAMED_COUNTERPARTY_PATTERN`` - the deterministic candidate the first
  decision packet sketched ('acquisition of <Name>', 'merger with <Name>',
  'business combination with <Name>', 'Agreement and Plan of Merger').
  Diagnostic only: nothing in the route uses it.

Zero network calls. Usage, from the repository root:
    python3 docs/evidence/issue47_history/e01-item-text/census.py
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext.deterministic_router import _hdr_item_codes, load_event_route_catalog  # noqa: E402
from vnext.historical_event_items import alias_occurrences, item_text  # noqa: E402

HERE = Path(__file__).resolve().parent
JUDGEMENTS = (REPO / "docs/evidence/issue47_history/e01-keyword-branch/eight-o-one-judgements.json",
              HERE / "more-eight-o-one-judgements.json")
NAMED = re.compile(r"\b(?:acquisition|merger|business combination)\s+(?:of|with)\s+[A-Z]"
                   r"|Agreement and Plan of Merger")
REPORTS = "REPORTS_A_TRANSACTION_THE_REGISTRANT_IS_PARTY_TO"


def saved_eight_o_ones():
    for folder in sorted((REPO / "evidence/accession_materials").iterdir()):
        headers = sorted(folder.glob("*.hdr.sgml"))
        if not headers:
            continue
        header = headers[0].read_bytes().decode("utf-8", "replace")
        form = re.search(r"<TYPE>\s*([^\r\n]+)", header)
        if form is None or form.group(1).strip() not in ("8-K", "8-K/A"):
            continue
        if "8.01" not in _hdr_item_codes(raw_bytes=headers[0].read_bytes()):
            continue
        accession = re.search(r"<ACCESSION-NUMBER>\s*([^\r\n]+)", header).group(1).strip()
        filed = re.search(r"<FILING-DATE>\s*([0-9]{8})", header).group(1)
        primary = [path for path in folder.iterdir() if path.suffix in (".htm", ".html")][0]
        yield folder.name, accession, filed, primary


def main():
    route = load_event_route_catalog(repo_root=REPO)["routes"]["E01"]
    aliases = [alias for rule in route["keyword_item_rules"] for alias in rule["aliases"]]
    judgements = {}
    for path in JUDGEMENTS:
        judgements.update(json.loads(path.read_text(encoding="utf-8"))["per_filing"])
    items = []
    for folder, accession, filed, primary in saved_eight_o_ones():
        text = item_text(raw_bytes=primary.read_bytes(), item_code="8.01")
        _, hits = alias_occurrences(text=text["text"], aliases=aliases)
        judgement = judgements[accession]
        items.append({
            "folder": folder, "accession": accession, "filed": filed,
            "primary_document": primary.name, "item_start": text["start"],
            "item_end": text["end"], "end_marker": text["end_marker"],
            "text_sha256": text["text_sha256"], "characters": len(text["text"]),
            "alias_occurrences": [{"alias": hit["alias"], "sentence": hit["sentence"]}
                                  for hit in hits],
            "judgement": judgement,
            "LITERAL_ALIAS_IN_THE_ITEM": bool(hits),
            "CONTENT_REPORTS_A_TRANSACTION": judgement["decision"] == REPORTS,
            "NAMED_COUNTERPARTY_PATTERN": bool(NAMED.search(text["text"]))})
    content = [item for item in items if item["CONTENT_REPORTS_A_TRANSACTION"]]
    summary = {"items": len(items), "judged": len(content) + sum(
        not item["CONTENT_REPORTS_A_TRANSACTION"] for item in items),
               "content_reports_a_transaction": sorted(item["accession"] for item in content),
               "of_which_no_alias_occurs": sorted(item["accession"] for item in content
                                                  if not item["LITERAL_ALIAS_IN_THE_ITEM"])}
    for reading in ("LITERAL_ALIAS_IN_THE_ITEM", "NAMED_COUNTERPARTY_PATTERN"):
        admitted = {item["accession"] for item in items if item[reading]}
        truth = set(summary["content_reports_a_transaction"])
        summary[reading] = {"admits": len(admitted), "agrees_with_the_judgement": len(admitted & truth),
                            "admits_what_the_judgement_does_not": sorted(admitted - truth),
                            "misses_what_the_judgement_admits": sorted(truth - admitted)}
    report = {"record_type": "ISSUE_47_E01_SAVED_EIGHT_O_ONE_CENSUS",
              "reader": "scripts/vnext/historical_event_items.py (item_text, alias_occurrences)",
              "aliases": aliases, "summary": summary, "items": items,
              "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (HERE / "census.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
