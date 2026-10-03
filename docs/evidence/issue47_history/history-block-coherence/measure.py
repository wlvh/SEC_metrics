"""Where do a submissions index's history blocks really end? Measured on every saved index.

The history catalog treats a block as coherent only when every filing in it is
dated inside the ``[filingFrom, filingTo]`` range the index declares for it.
JPMorgan's periods stayed blocked by that rule after its index and all 69
history blocks were acquired fresh, within two minutes of each other, so the
refusal could not be a stale snapshot. This reads, for every saved index (the
latest saved copy of each URL, from the checkout or else from the
acquisition's export):

* the gap between each block's declared end and the declared start of the next
  newer block (the newest block's next newer block is the index's own recent
  list, whose start is its oldest filing date);
* for every saved block, how far outside its declared range each filing lies,
  and whether its row count equals the ``filingCount`` the index declares;
* which filings the catalog's metadata parser keeps, since only those can be
  reported as out of range by the catalog;
* for every undeclared gap day, the filings on it by form, and whether it is
  the first day of a fiscal year (the day after a 10-K report date the saved
  metadata lists) - the one place a window selected by declared ranges would
  skip the block that holds the day.

Usage (from the checkout): python3 measure.py <out.json>
Zero requests.
"""
import collections
import csv
import datetime
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import saved_bytes  # noqa: E402
from vnext.normal_governance_input import (NormalGovernanceInputError,  # noqa: E402
                                           _filings, history_body_alignment)

DAY = datetime.timedelta(days=1)


def _date(text):
    return datetime.date.fromisoformat(text[:10])


def _latest_saved(repo_root):
    """The latest successful saved attempt of every submissions URL.

    The checkout's own ledger lists what it saved; the acquisition's attempts
    are carried by the export, each with the headers file saved beside it,
    which names the URL and the save time. Later wins.
    """
    rows = {}
    with open(repo_root / "evidence" / "requests_log.csv", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if "/submissions/" in row["source_url"] and row["status_code"] == "200":
                rows[row["source_url"]] = {"repo_relative_path": row["repo_relative_path"],
                                           "timestamp_utc": row["timestamp_utc"]}
    if (repo_root / "evidence" / "issue47_acquired" / "export.json").exists():
        from acceptance_readings import _export_member_bytes, _export_members
        members = _export_members(repo_root)
        for member in sorted(members):
            if not member.endswith(".headers.json") or "/submissions/" in member:
                continue
            headers = json.loads(_export_member_bytes(repo_root=repo_root, member=member,
                                                      members=members))
            if "/submissions/" not in headers["url"] or headers["status_code"] != 200:
                continue
            body = member.rsplit("/", 1)[0] + "/" + headers["url"].rsplit("/", 1)[-1]
            current = rows.get(headers["url"])
            if current is None or current["timestamp_utc"] < headers["saved_at_utc"]:
                rows[headers["url"]] = {"repo_relative_path": body[len("source-inputs/"):],
                                        "timestamp_utc": headers["saved_at_utc"]}
    return rows


def main(out):
    saved = _latest_saved(REPO)
    indexes = {url: row for url, row in saved.items() if "-submissions-" not in url}
    report = {}
    for url, row in sorted(indexes.items()):
        payload = json.loads(saved_bytes(repo_root=REPO, relative=row["repo_relative_path"]))
        files = payload.get("filings", {}).get("files", [])
        recent = payload.get("filings", {}).get("recent", {}).get("filingDate", [])
        if not files:
            continue
        base = url.rsplit("/", 1)[0] + "/"
        gaps, blocks = collections.Counter(), []
        for position, block in enumerate(files):
            newer_start = (_date(files[position - 1]["filingFrom"]) if position
                           else (_date(min(recent)) if recent else None))
            gap = (newer_start - _date(block["filingTo"])).days if newer_start else None
            gaps[str(gap)] += 1
            entry = {"name": block["name"], "declared_from": block["filingFrom"],
                     "declared_to": block["filingTo"], "declared_count": block["filingCount"],
                     "next_newer_start": str(newer_start) if newer_start else None,
                     "gap_days": gap}
            source = saved.get(base + block["name"])
            if source is not None:
                body = json.loads(saved_bytes(repo_root=REPO, relative=source["repo_relative_path"]))
                offsets = collections.Counter()
                for date in body["filingDate"]:
                    value = _date(date)
                    if value > _date(block["filingTo"]):
                        offsets["after_declared_end+" + str((value - _date(block["filingTo"])).days)] += 1
                    elif value < _date(block["filingFrom"]):
                        offsets["before_declared_start-" + str((_date(block["filingFrom"]) - value).days)] += 1
                try:
                    kept = _filings(body, inventory_name=block["name"])
                    frozen = history_body_alignment(shard=block, rows=kept)
                    kept_status = {"kept_rows": len(kept),
                                   "frozen_rule_out_of_range": len(frozen["out_of_range_filings"]) if frozen else 0}
                except NormalGovernanceInputError as error:
                    kept_status = {"metadata_parser_refused": str(error)}
                entry.update(saved=True, fetched_utc=source["timestamp_utc"],
                             rows=len(body["filingDate"]),
                             count_matches_declared=len(body["filingDate"]) == block["filingCount"],
                             outside_declared_range=dict(offsets),
                             inside_declared_start_to_next_newer_start=all(
                                 _date(block["filingFrom"]) <= _date(d)
                                 and (newer_start is None or _date(d) < newer_start)
                                 for d in body["filingDate"]),
                             **kept_status)
            else:
                entry["saved"] = False
            blocks.append(entry)
        annual_ends = set(payload["filings"]["recent"].get("reportDate", [])[i]
                          for i, form in enumerate(payload["filings"]["recent"]["form"])
                          if form in ("10-K", "10-K/A"))
        holes = []
        for position, block in enumerate(files):
            entry = blocks[position]
            if entry["gap_days"] != 2 or not entry["saved"]:
                continue
            hole = str(_date(block["filingTo"]) + DAY)
            source = saved[base + block["name"]]
            body = json.loads(saved_bytes(repo_root=REPO, relative=source["repo_relative_path"]))
            forms = collections.Counter(form for form, date in zip(body["form"], body["filingDate"])
                                        if date == hole)
            for form, report_date in zip(body["form"], body.get("reportDate", [])):
                if form in ("10-K", "10-K/A") and report_date:
                    annual_ends.add(report_date)
            holes.append({"block": block["name"], "gap_day": hole, "filings_by_form": dict(forms)})
        starts = {str(_date(end) + DAY) for end in annual_ends if end}
        for hole in holes:
            hole["first_day_of_a_fiscal_year"] = hole["gap_day"] in starts
        saved_blocks = [b for b in blocks if b["saved"]]
        report[url.rsplit("/", 1)[-1]] = {
            "fetched_utc": row["timestamp_utc"], "declared_blocks": len(files),
            "gap_days_between_declared_ranges": dict(gaps),
            "saved_blocks": len(saved_blocks),
            "saved_blocks_with_rows_after_declared_end": sum(
                1 for b in saved_blocks if b.get("outside_declared_range")),
            "saved_blocks_every_row_before_next_newer_start": sum(
                1 for b in saved_blocks if b["inside_declared_start_to_next_newer_start"]),
            "saved_blocks_count_matches": sum(1 for b in saved_blocks if b["count_matches_declared"]),
            "gap_days_with_filings": sum(1 for h in holes if h["filings_by_form"]),
            "gap_days_that_start_a_fiscal_year_with_filings": [
                h for h in holes if h["first_day_of_a_fiscal_year"] and h["filings_by_form"]],
            "gap_days": holes, "blocks": blocks}
    Path(out).write_text(json.dumps({"record_type": "ISSUE_47_SUBMISSIONS_BLOCK_BOUNDARIES",
                                     "indexes": report, "calls": {"provider": 0, "paid": 0, "sec": 0}},
                                    indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for name, entry in report.items():
        print(name, {k: v for k, v in entry.items() if k != "blocks"})


if __name__ == "__main__":
    main(sys.argv[1])
