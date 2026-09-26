"""Read CEO pay (C03) and the auditor-change flag (C04) out of the source documents.

C03's approved source is the annual meeting's DEF 14A, preferring the ecd
pay-versus-performance facts; the route pins the proxy to the period rather
than taking the latest. This reads the ecd PEO total for the target period
out of every saved proxy of the registrant and accepts only where exactly one
proxy reports exactly one PEO total for that period.

C04 is the auditor change. Zero means the registrant did not change auditors,
and two things say so independently: the AuditorName tagged in this year's
10-K and in the previous year's name the same firm, and no 8-K in the window
carries item 4.01 (from the event-count reading, so the two readings cannot
disagree about the same filings).

It replaces a reading whose code was never committed; that copy also parsed
numbers with int() and skipped what failed, the defect that hid a fact from
the statement reading. Here numbers are decimals and an unparseable one is
listed. Published values come from a named runs root and closure.

Usage:
    python3 tools/read_governance_facts.py --runs-root <flat runs root> \
        --closure sha256:<closure the compared results ran under>
"""
import argparse
import collections
import glob
import html
import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

OUT = "docs/evidence/issue47_history/content-acceptance/governance-read.json"
EVENTS = "docs/evidence/issue47_history/content-acceptance/event-count-read.json"
CASES = [("marriott_international", "2025-12-31", "marriott-2025"),
         ("ford_motor_company", "2025-12-31", "ford-2025"),
         ("pfizer", "2025-12-31", "pfizer-2025"),
         ("lumen_technologies", "2025-12-31", "lumen-2025"),
         ("enphase_energy", "2025-12-31", "enphase-2025"),
         ("southwest_airlines", "2025-12-31", "southwest-2025"),
         ("salesforce", "2026-01-31", "salesforce-2026"),
         ("macys", "2026-01-31", "macys-2026")]
UNREAD = []


def contexts_of(text):
    """Contexts, whatever namespace prefix the document happens to use.

    Two versions of this were wrong in the same way and neither said so. The
    first required the <xbrli:> prefix; the second required id to be the first
    attribute, and Marriott's proxy writes <xbrli:context xmlns="" id="c1">.
    Both returned an empty map, and an empty map reads exactly like a document
    with no facts - which is how six of eight C03 positions came back
    NOT_READ.
    """
    found = {}
    for block in re.finditer(r"<(?:[A-Za-z0-9]+:)?context\b([^>]*)>(.*?)"
                             r"</(?:[A-Za-z0-9]+:)?context>", text, re.S):
        head, inner = block.group(1), block.group(2)
        identifier = re.search(r"\bid=\"([^\"]+)\"", head)
        if identifier is None:
            continue
        cid = identifier.group(1)
        start = re.search(r"<(?:[A-Za-z0-9]+:)?startDate>([^<]+)<", inner)
        end = re.search(r"<(?:[A-Za-z0-9]+:)?endDate>([^<]+)<", inner)
        instant = re.search(r"<(?:[A-Za-z0-9]+:)?instant>([^<]+)<", inner)
        found[cid] = {"start": start.group(1) if start else None,
                      "end": end.group(1) if end else (instant.group(1) if instant else None),
                      "members": sorted(member.strip() for member in re.findall(
                          r"<(?:[A-Za-z0-9]+:)?explicitMember[^>]*>([^<]+)<", inner)),
                      "dimensional": bool(re.search(
                          r"<(?:[A-Za-z0-9]+:)?explicitMember", inner))}
    return found


def peo_totals(text, contexts):
    """Every ecd:PeoTotalCompAmt with its period, person and how it is shown."""
    totals = []
    for tag in re.finditer(r"<ix:nonFraction([^>]*)>(.*?)</ix:nonFraction>", text, re.S):
        attrs = dict(re.findall(r"([a-zA-Z:\-]+)=\"([^\"]*)\"", tag.group(1)))
        if attrs.get("name") != "ecd:PeoTotalCompAmt":
            continue
        context = contexts.get(attrs.get("contextRef"))
        if context is None:
            continue
        shown = html.unescape(re.sub(r"<[^>]+>", "", tag.group(2))).strip()
        placeholder = attrs.get("format", "").endswith("fixed-zero")
        if placeholder:
            value = Decimal(0)
        else:
            try:
                value = Decimal(shown.replace(",", ""))
            except InvalidOperation:
                UNREAD.append({"concept": "ecd:PeoTotalCompAmt",
                               "context": attrs.get("contextRef"), "shown": shown[:40]})
                continue
            value *= Decimal(10) ** int(attrs.get("scale", "0") or 0)
        totals.append({"key": (context["start"], context["end"]),
                       "members": context["members"], "value": value,
                       "placeholder": placeholder, "shown": shown})
    return totals


def peo_totals_for(totals, key):
    """The period's PEO totals, less the table's placeholders for other years' PEOs.

    A pay-versus-performance table has a column per person who was PEO in any
    of its years, and a year that person did not serve shows the SEC's
    fixed-zero dash. Counted as a value, that dash is a second PEO total of $0
    - which is how a first version of this reading refused Southwest, whose
    2025 row carries a dash for Gary C. Kelly beside Robert E. Jordan's total.
    The table itself says what the dash is: the same person's total is
    non-zero only in other years. So a fixed-zero dash for a person with a
    non-zero total in another period is a placeholder and is set aside, with
    the evidence; anything else - including a dash for a person who is never
    paid in the table - still counts.

    Returns:
        ``(kept, set_aside)``.
    """
    kept, set_aside = [], []
    for total in totals:
        if total["key"] != key:
            continue
        paid_elsewhere = sorted({other["key"][0][:4] for other in totals
                                 if other["members"] == total["members"]
                                 and other["key"] != key and other["value"] != 0})
        if total["placeholder"] and total["members"] and paid_elsewhere:
            entry = {"members": total["members"], "shown": total["shown"],
                     "same_person_paid_as_peo_in": paid_elsewhere}
            if entry not in set_aside:
                set_aside.append(entry)
        else:
            kept.append(total)
    return kept, set_aside


def text_fact(text, concept):
    """A named text fact, whether the document is inline XBRL or an instance.

    Only the inline form was handled. An XBRL instance writes the fact as a
    plain element - <dei:AuditorName contextRef="c-1">DELOITTE &amp; TOUCHE
    LLP</dei:AuditorName> - and has no ix:nonNumeric at all, so reading one
    returned an empty set. That is indistinguishable from a filing that does
    not name an auditor, which is the shape this round kept producing; it was
    caught here only because the finder was checked against a document already
    known to contain the fact.
    """
    values, prefix, local = set(), *concept.split(":", 1)
    for tag in re.finditer(r"<ix:nonNumeric([^>]*)>(.*?)</ix:nonNumeric>", text, re.S):
        attrs = dict(re.findall(r"([a-zA-Z:\-]+)=\"([^\"]*)\"", tag.group(1)))
        if attrs.get("name") == concept:
            values.add(tag.group(2))
    for tag in re.finditer(r"<[A-Za-z0-9]*:?" + re.escape(local)
                           + r"\b([^>]*)>(.*?)</[A-Za-z0-9]*:?" + re.escape(local) + r">",
                           text, re.S):
        values.add(tag.group(2))
    cleaned = set()
    for raw in values:
        plain = re.sub(r"<[^>]+>", " ", raw)
        plain = re.sub(r"\s+", " ", unicodedata.normalize("NFKC",
                                                          html.unescape(plain))).strip()
        if plain:
            cleaned.add(plain)
    return sorted(cleaned)


def proxy_documents(cik):
    """Saved DEF 14A primary documents of this registrant, identified by form.

    The previous version globbed ``*def14a*.htm`` inside the registrant's
    accession material directories. Exactly one of the ten companies names its
    proxy that way - Ford's ``e26003_f-def14a.htm``; the rest use
    ``<ticker>-<date>.htm``. So the glob could only ever find Ford, and the
    four filings it missed were reported as
    NO_SAVED_PROXY_REPORTS_THE_TARGET_PERIOD, which reads as missing material.
    They were saved the whole time, carrying 76 to 138 ecd facts each.

    Returns both what the registrant declares and what is on disk, because
    "this registrant files no proxy", "the proxy is not saved" and "the saved
    proxy does not report this period" are three different answers and the
    caller has to be able to tell them apart.
    """
    padded = "CIK" + str(int(cik)).zfill(10)
    declared, seen = [], set()
    for blob in sorted((REPO / "evidence/submissions").glob(padded + "*.json")):
        if blob.name.endswith(".headers.json"):
            continue
        try:
            payload = json.loads(blob.read_text(encoding="utf-8"))
        except ValueError:
            continue
        recent = (payload.get("filings") or {}).get("recent")
        for group in ([recent] if isinstance(recent, dict) else []) + (
                [payload] if isinstance(payload.get("form"), list) else []):
            for index, form in enumerate(group.get("form") or []):
                if form != "DEF 14A":
                    continue
                accession = group["accessionNumber"][index]
                if accession in seen:
                    continue
                seen.add(accession)
                declared.append({"accession": accession,
                                 "primary": group["primaryDocument"][index],
                                 "filing_date": group["filingDate"][index]})
    documents = []
    for row in declared:
        digits = row["accession"].replace("-", "")
        for directory in sorted(glob.glob(str(REPO / "evidence/accession_materials")
                                          + "/*_" + str(int(cik)) + "_" + digits)):
            candidate = Path(directory) / row["primary"]
            if candidate.exists():
                documents.append(candidate)
    return declared, sorted(documents)


def _auditor_names_in_accession(*, cik, accession, primary=None):
    """dei:AuditorName from a saved document of this accession.

    Returns (names, repository path) or ([], None). The primary document is
    tried first because it is the one the route prefers, then the XBRL
    instance beside it: five positions read as PREVIOUS_YEARS_FILING_NOT_
    READABLE while the route produced a value, and the cause was that this
    reading demanded the primary HTML. Enphase's prior accession holds
    enph-20241231_htm.xml and index.json and no primary HTML at all.

    This widens which document is read, not which filing - the accession is
    the one the period selection already chose.
    """
    digits = accession.replace("-", "")
    for directory in sorted(glob.glob(str(REPO / "evidence/accession_materials")
                                      + "/*_" + str(int(cik)) + "_" + digits)):
        candidates = []
        if primary and (Path(directory) / primary).exists():
            candidates.append(Path(directory) / primary)
        candidates.extend(sorted(Path(directory).glob("*_htm.xml")))
        for candidate in candidates:
            names = text_fact(candidate.read_text(encoding="utf-8-sig",
                                                  errors="replace"),
                              "dei:AuditorName")
            if names:
                return names, str(candidate.relative_to(REPO))
    return [], None


def _number(value):
    """A decimal as JSON: an integer where it is one, else its string."""
    return int(value) if value == value.to_integral_value() else str(value)


def read_case(*, company_id, label, period, cik, source_document, selection,
              published, event_items):
    """C03 and C04 for one pinned period, read from the saved documents.

    Args:
        period: ``{"period_start", "period_end"}``.
        cik: The registrant's CIK as a string of digits.
        source_document: Repository path of the target annual report.
        selection: The pinned period selection (names the prior filing).
        published: ``{"C03": value or None, "C04": value or None}``.
        event_items: The window's filings with their item codes.
    """
    prior = selection.get("prior_filing") or {}
    entry = {"company_id": company_id,
             "period": [period["period_start"], period["period_end"]],
             # What the reading was pointed at, so it re-derives from the saved
             # documents without asking the period selection again.
             "target_document": source_document, "cik": cik,
             "prior_filing": {key: prior.get(key) for key in
                              ("accessionNumber", "primaryDocument")} if prior else None}
    hits = []
    declared, documents = proxy_documents(cik)
    key = (period["period_start"], period["period_end"])
    for path in documents:
        raw = Path(path).read_text(encoding="utf-8-sig", errors="replace")
        kept, set_aside = peo_totals_for(peo_totals(raw, contexts_of(raw)), key)
        # A PEO total tagged in a context naming the officer is still one
        # number when there is only one of it; ambiguity is several.
        if kept or set_aside:
            hit = {"proxy": str(Path(path).relative_to(REPO)),
                   "values": [_number(v) for v in sorted({t["value"] for t in kept})],
                   "per_officer_tagged": bool(kept) and all(t["members"] for t in kept)}
            if set_aside:
                hit["placeholders_set_aside"] = set_aside
            hits.append(hit)
    value = None
    # One proxy, one value. Several PEO totals for a year (a CEO transition)
    # are not chosen between.
    if len(hits) == 1 and len(hits[0]["values"]) == 1:
        value = Decimal(hits[0]["values"][0])
    c03 = published.get("C03")
    entry["C03"] = {"published": c03, "read": str(value) if value is not None else None,
                    "proxies_reporting_the_target_period": hits,
                    "why_not_read": (
                        None if value is not None
                        else "SEVERAL_PEO_TOTALS_FOR_THE_TARGET_PERIOD" if hits
                        else "NO_SAVED_PROXY_DOCUMENT_FOR_ANY_DECLARED_DEF14A"
                        if declared and not documents
                        else "THE_REGISTRANT_DECLARES_NO_DEF14A" if not declared
                        else "NO_SAVED_PROXY_REPORTS_THE_TARGET_PERIOD"),
                    "def14a_declared": len(declared),
                    "def14a_documents_saved": len(documents),
                    "verdict": ("NO_PUBLISHED_VALUE" if c03 is None
                                else "NOT_READ" if value is None
                                else "MATCH" if value == Decimal(c03) else "DIFFERS")}
    names = {"target": text_fact((REPO / source_document).read_text(
        encoding="utf-8-sig", errors="replace"), "dei:AuditorName")}
    # The prior filing is the one the period selection names; recomputing it
    # was the source of two earlier defects (a truncated error string, and a
    # prior period end made by replacing the year - a date a 52/53-week
    # filer's calendar never had).
    prior_names, prior_note, prior_read_from = [], None, None
    prior_filing = selection.get("prior_filing") or {}
    if not prior_filing.get("accessionNumber"):
        prior_note = "THE_SELECTION_NAMES_NO_PRIOR_FILING"
    else:
        prior_names, prior_read_from = _auditor_names_in_accession(
            cik=cik, accession=prior_filing["accessionNumber"],
            primary=prior_filing.get("primaryDocument"))
        if not prior_names:
            prior_note = ("NO_SAVED_DOCUMENT_OF_THE_PRIOR_ACCESSION_NAMES_AN_AUDITOR:"
                          + prior_filing["accessionNumber"])
    four_o_one = [f["accession"] for f in event_items if "4.01" in f["items"]]

    # Macy's names the same firm "KPMG LLP" and "KPMG, LLP". A difference of
    # punctuation and case is the same firm - the route's judgement too, so
    # both exact strings are recorded beside it.
    def firm(name):
        return "".join(c for c in name.casefold() if c.isalnum())

    same_firm = (bool(names["target"]) and bool(prior_names)
                 and sorted(map(firm, names["target"])) == sorted(map(firm, prior_names)))
    spelled_differently = same_firm and sorted(names["target"]) != sorted(prior_names)
    value = None
    if names["target"] and prior_names and not prior_note:
        value = Decimal(0) if (same_firm and not four_o_one) else None
    c04 = published.get("C04")
    entry["C04"] = {"published": c04,
                    "auditor_named_in_the_target_filing": names["target"],
                    "auditor_named_in_the_previous_years_filing": prior_names,
                    "previous_year_read_from": prior_read_from,
                    "previous_year_note": prior_note,
                    "eight_k_item_4_01_in_window": four_o_one,
                    "the_two_filings_spell_the_firm_differently": spelled_differently,
                    "read": str(value) if value is not None else None,
                    "why_not_read": (None if value is not None
                                     else "PREVIOUS_YEARS_FILING_NOT_READABLE"),
                    "verdict": ("NO_PUBLISHED_VALUE" if c04 is None
                                else "NOT_READ" if value is None
                                else "MATCH" if value == Decimal(c04) else "DIFFERS")}
    return entry


def _case_input(*, company_id, report_end):
    from vnext.historical_annual_input import prepare_historical_annual_input
    from vnext.normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                         report_end=report_end)
    prepared = prepare_historical_annual_input(repo_root=REPO, company_id=company_id,
                                               period_selection=selection)
    return (selection, prepared["original_input"]["table_input"]["target_period"],
            str(int(prepared["entity"])),
            prepared["original_input"]["table_input"]["source_repo_relative_path"])


def main():
    from acceptance_readings import accession_of_document
    from bind_acceptance_readings import identity_for
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    events = json.loads((REPO / EVENTS).read_text(encoding="utf-8"))["per_position"]
    previous = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    positions = {}
    for company_id, report_end, label in CASES:
        selection, period, cik, document = _case_input(company_id=company_id,
                                                       report_end=report_end)
        published = {}
        for metric in ("C03", "C04"):
            result = select_receipt(found=index.get((company_id, metric, report_end), []),
                                    closure=arguments.closure)["result"]
            published[metric] = (None if result is None or result.get("value") is None
                                  else str(result["value"]))
        entry = read_case(company_id=company_id, label=label, period=period, cik=cik,
                          source_document=document, selection=selection,
                          published=published,
                          event_items=events.get(label, {}).get("filings", {}).get(
                              "filing_date", []))
        for metric in ("C03", "C04"):
            row = entry[metric]
            if row["published"] is None:
                continue
            if metric == "C03":
                named = [accession_of_document(repo_root=REPO, document=hit["proxy"])[0]
                         for hit in row["proxies_reporting_the_target_period"]]
            else:
                named = ([accession_of_document(repo_root=REPO,
                                                document=row["previous_year_read_from"])[0]]
                         if row["previous_year_read_from"] else [])
            identity, refusal = identity_for(
                position={"company_id": company_id, "metric_id": metric,
                          "period_end": report_end, "published": row["published"],
                          "reading_filings": named, "reading_window": entry["period"],
                          "filings_are_the_whole_set": False},
                index=index, closure=arguments.closure)
            if refusal is not None:
                raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + metric + ":" + refusal)
            identity["established_by"] = "RECORDED_AT_READING_TIME"
            row["checked_identity"] = identity
        positions[label] = entry
        print(label, "C03", entry["C03"]["verdict"], "C04", entry["C04"]["verdict"], flush=True)
    owned = {"per_position", "read_against_batch", "reader", "requirement_closure_hash",
             "needed_facts_not_read", "calls"}
    body = {key: value for key, value in previous.items() if key not in owned}
    body.update({"reader": "tools/read_governance_facts.py",
                 "requirement_closure_hash": arguments.closure,
                 "needed_facts_not_read": UNREAD, "per_position": positions,
                 "calls": {"provider": 0, "paid": 0, "sec": 0}})
    (REPO / OUT).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False)
                            + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
