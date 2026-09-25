"""Where each content reading keeps its per-position conclusions.

Eight shapes: a statement read keyed by label with one row per metric, a
lodging table keyed by label, an event window with its filing list, E01's
item 8.01 reading over the same windows, governance rows beside a period, a D02
text reading, the D01 heading readings (one shape, three files), and two
single-coordinate readings. The acceptance register and the identity binder both have to walk
them, and walking them twice with two sets of rules is how the two would come
to disagree about which positions exist. So the walk is here, once.

For every position that compared a published value, a walk yields:

* the coordinate - company, metric, period end - and the value it compared;
* what the reading itself names about the object it checked - the filings it
  opened and, where it records one, the window it read - so that a binding can
  be checked against the reading rather than taken from a result;
* ``slot``, the dict inside the loaded reading where that position's
  ``checked_identity`` lives.

Nothing here decides whether a position is accepted; that is the register's
rule. This only says what each reading contains and where.
"""
import json
import re
from pathlib import Path

EVIDENCE = "docs/evidence/issue47_history/content-acceptance/"
CROSS = EVIDENCE + "cross-source-read.json"
LODGING = EVIDENCE + "lodging-table-read.json"
EVENTS = EVIDENCE + "event-count-read.json"
# E01 counts an 8.01 only once a keyword in its text confirms it, which a count
# of header item codes cannot check. Every 8.01 in the E01 windows is read here
# by tools/read_e01_eight_o_ones.py, under each reading of that confirmation.
E01_EIGHT_O_ONES = EVIDENCE + "e01-eight-o-one-read.json"
GOVERNANCE = EVIDENCE + "governance-read.json"
TEXT = EVIDENCE + "d02-both-directions-read.json"
# D01 is read off each filing's bytes by tools/read_d01_headings.py, which
# imports none of the route's text modules: one reading for the 30-metric
# batch's results, one for the three results the underline repair produced and
# one for Paramount's result after the short-gap repair. The earlier
# d01-headings-read.json stays as a record of what it found, and is not a
# source of acceptances: its "judged" list was the selector's own output, so it
# could not have told a repaired selector from an unrepaired one.
HEADINGS = EVIDENCE + "d01-headings-read-from-bytes.json"
HEADINGS_FROM_BYTES = EVIDENCE + "d01-marriott-repaired-read.json"
HEADINGS_PARAMOUNT_REPAIRED = EVIDENCE + "d01-paramount-repaired-read.json"
D01_READINGS = (HEADINGS, HEADINGS_FROM_BYTES, HEADINGS_PARAMOUNT_REPAIRED)
RPO = EVIDENCE + "rpo-read.json"
COMPENSATION = EVIDENCE + "paramount-compensation-table-read.json"
READINGS = (CROSS, LODGING, EVENTS, E01_EIGHT_O_ONES, GOVERNANCE, TEXT, *D01_READINGS, RPO,
            COMPENSATION)
# The readings key some positions by a label only. The label is what the
# reading recorded, and this is the period each label names.
PERIODS = {"marriott-2025": "2025-12-31", "marriott-2024": "2024-12-31",
           "marriott-2023": "2023-12-31", "ford-2025": "2025-12-31",
           "pfizer-2025": "2025-12-31", "lumen-2025": "2025-12-31",
           "enphase-2025": "2025-12-31", "southwest-2025": "2025-12-31",
           "salesforce-2026": "2026-01-31", "macys-2026": "2026-01-31",
           "paramount-2025": "2025-12-31", "jpmorgan-2025": "2025-12-31"}
_ACCESSION_DIRECTORY = re.compile(r"_(\d+)_(\d{10})(\d{2})(\d{6})\Z")
_ARCHIVE_URL = re.compile(r"/Archives/edgar/data/(\d+)/(\d{10})(\d{2})(\d{6})/")


class ReadingError(ValueError):
    """A reading names something this walk cannot resolve."""


def load(*, repo_root: Path, path: str):
    """The reading's body and the exact serialisation it was written with.

    A reading is rewritten in place when its identities are bound, and a
    rewrite that reformatted it would move its hash for no reason a reader can
    see. So the parameters that reproduce the original bytes are found rather
    than assumed, and a reading written some other way is refused.
    """
    raw = (repo_root / path).read_text(encoding="utf-8")
    body = json.loads(raw)
    for indent in (1, 2, None):
        for sort_keys in (True, False):
            options = {"indent": indent, "sort_keys": sort_keys, "ensure_ascii": False}
            if json.dumps(body, **options) + "\n" == raw:
                return body, options
    raise ReadingError("READING_SERIALISATION_NOT_REPRODUCIBLE:" + path)


def dump(*, repo_root: Path, path: str, body, options):
    """Write a reading back with the serialisation it was read with."""
    (repo_root / path).write_text(json.dumps(body, **options) + "\n", encoding="utf-8")


def accession_of_document(*, repo_root: Path, document: str):
    """The filing a saved document belongs to, from what was saved with it.

    Two layouts hold saved documents. An accession-materials directory is named
    ``<company>_<cik>_<accession digits>``. A request attempt is named by its
    content hash, and the URL it was fetched from is in the headers saved
    beside it. Either way the answer comes from the saved material, not from a
    result.

    Returns:
        ``(accession, cik)``.
    """
    marker = document.find("evidence/")
    if marker < 0:
        raise ReadingError("READING_DOCUMENT_NOT_UNDER_EVIDENCE:" + document)
    relative = Path(document[marker:])
    if relative.parts[1] == "accession_materials":
        found = _ACCESSION_DIRECTORY.search(relative.parts[2])
        if found is None:
            raise ReadingError("READING_DOCUMENT_DIRECTORY_NAMES_NO_ACCESSION:" + document)
        cik, head, year, serial = found.groups()
        return head + "-" + year + "-" + serial, str(int(cik))
    if relative.parts[1] == "request_attempts":
        headers = sorted((repo_root / relative.parent).glob(relative.name + ".*.headers.json"))
        if len(headers) != 1:
            raise ReadingError("READING_ATTEMPT_HEADERS_NOT_UNIQUE:" + document)
        url = json.loads(headers[0].read_text(encoding="utf-8"))["url"]
        found = _ARCHIVE_URL.search(url)
        if found is None:
            raise ReadingError("READING_ATTEMPT_URL_NAMES_NO_ACCESSION:" + url)
        cik, head, year, serial = found.groups()
        return head + "-" + year + "-" + serial, str(int(cik))
    raise ReadingError("READING_DOCUMENT_LAYOUT_UNKNOWN:" + document)


def _position(*, reading, label, slot, company_id, metric_id, period_end, published,
              verdict, filings=(), window=None, filings_are_the_whole_set=False, case=None):
    return {"reading": reading, "label": label, "slot": slot,
            # The record the slot sits in, for the reading-specific locators a
            # register entry quotes. The same object as ``slot`` where the
            # reading keeps one record per position.
            "case": slot if case is None else case,
            "company_id": company_id, "metric_id": metric_id,
            "period_end": period_end, "published": published, "verdict": verdict,
            # What the reading itself names. A binding must agree with it.
            "reading_filings": sorted(set(filings)),
            "reading_window": list(window) if window else None,
            # True where the reading enumerated every filing it counted - the
            # event windows - so the result's filing set must equal it rather
            # than merely contain it.
            "filings_are_the_whole_set": filings_are_the_whole_set}


def positions(*, repo_root: Path, path: str, body):
    """Every position in this reading that compared a published value."""
    found = []
    if path == CROSS:
        for label, case in sorted(body["per_position"].items()):
            if "error" in case:
                continue
            accession, _ = accession_of_document(repo_root=repo_root,
                                                 document=case["document"])
            for metric, row in sorted(case["metrics"].items()):
                if row.get("published") is None:
                    continue
                found.append(_position(
                    reading=path, label=label, slot=row, company_id=case["company_id"],
                    metric_id=metric, period_end=case["period_end"],
                    published=row["published"], verdict=row["verdict"],
                    filings=[accession], case=case))
    elif path == LODGING:
        for label, case in sorted(body.items()):
            accession, _ = accession_of_document(repo_root=repo_root,
                                                 document=case["document"])
            for metric in ("B10", "B11"):
                row = case.get(metric)
                if row is None or row.get("published") is None:
                    continue
                found.append(_position(
                    reading=path, label=label, slot=row,
                    company_id="marriott_international", metric_id=metric,
                    period_end=PERIODS[label], published=row["published"],
                    verdict=row["verdict"], filings=[accession], case=case))
    elif path == EVENTS:
        for label, case in sorted(body["per_position"].items()):
            if "metrics" not in case:
                continue
            listed = [filing["accession"] for filing in case["filings"]["filing_date"]]
            for metric, row in sorted(case["metrics"].items()):
                if row.get("published") is None:
                    continue
                found.append(_position(
                    reading=path, label=label, slot=row, company_id=case["company_id"],
                    metric_id=metric, period_end=PERIODS[label],
                    published=row["published"], verdict=row["verdict"],
                    filings=listed, window=case["window"],
                    filings_are_the_whole_set=True, case=case))
    elif path == E01_EIGHT_O_ONES:
        for label, case in sorted(body["per_position"].items()):
            found.append(_position(
                reading=path, label=label, slot=case, company_id=case["company_id"],
                metric_id="E01", period_end=case["period_end"],
                published=case["published"], verdict=case["verdict"],
                filings=case["filings_in_window"], window=case["window"],
                filings_are_the_whole_set=True))
    elif path == GOVERNANCE:
        for label, case in sorted(body["per_position"].items()):
            for metric in ("C03", "C04"):
                row = case.get(metric)
                if row is None or row.get("published") is None:
                    continue
                if metric == "C03":
                    named = [accession_of_document(repo_root=repo_root,
                                                   document=proxy["proxy"])[0]
                             for proxy in row.get("proxies_reporting_the_target_period") or ()]
                else:
                    named = ([accession_of_document(
                        repo_root=repo_root, document=row["previous_year_read_from"])[0]]
                        if row.get("previous_year_read_from") else [])
                found.append(_position(
                    reading=path, label=label, slot=row, company_id=case["company_id"],
                    metric_id=metric, period_end=PERIODS[label],
                    published=row["published"], verdict=row.get("verdict"),
                    filings=named, window=case.get("period"), case=case))
    elif path == TEXT:
        # Every position this reading holds was read whole and accepted; the
        # sets found wrong are recorded as defects, not here. It names the
        # value by digest and names no filing.
        for label, case in sorted(body["per_position"].items()):
            found.append(_position(
                reading=path, label=label, slot=case, company_id=case["company_id"],
                metric_id="D02", period_end=case["period_end"],
                published=case["value_sha256"], verdict="MATCH"))
    elif path in D01_READINGS:
        for label, case in sorted(body["per_position"].items()):
            if not case.get("value_sha256"):
                continue
            found.append(_position(
                reading=path, label=label, slot=case, company_id=case["company_id"],
                metric_id="D01", period_end=case["period_end"],
                published=case["value_sha256"], verdict=case["verdict"],
                filings=[case["accession"]] if case.get("accession") else []))
    elif path == RPO:
        found.append(_position(
            reading=path, label="salesforce-2026", slot=body,
            company_id=body["company_id"], metric_id=body["metric_id"],
            period_end=body["period_end"], published=body["published"],
            verdict=body["verdict"]))
    elif path == COMPENSATION:
        accession, _ = accession_of_document(repo_root=repo_root, document=body["document"])
        found.append(_position(
            reading=path, label="paramount-2025", slot=body,
            company_id=body["company_id"], metric_id="C03",
            period_end=body["period_end"], published=body["published"],
            verdict=body["verdict"], filings=[accession]))
    else:
        raise ReadingError("READING_SHAPE_UNKNOWN:" + path)
    return found
