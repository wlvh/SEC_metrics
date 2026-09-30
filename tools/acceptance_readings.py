"""Where each content reading keeps its per-position conclusions.

Nine shapes: a statement read keyed by label with one row per metric, a
lodging table keyed by label, an event window with its filing list, E01's
item 8.01 reading over the same windows, governance rows beside a period, a D02
text reading, the D01 heading readings (one shape, three files), an older
year's C03 read across every proxy that reports it, and two single-coordinate
readings. The acceptance register and the identity binder both have to walk
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
import hashlib
import json
import re
import tarfile
from pathlib import Path

EVIDENCE = "docs/evidence/issue47_history/content-acceptance/"
CROSS = EVIDENCE + "cross-source-read.json"
# Paramount's two Part III years, read the same way against the targeted Runs of
# the closure that admitted their statement inputs (part-iii-statement-review/).
CROSS_PARAMOUNT_PART_III = EVIDENCE + "part-iii-statement-read.json"
# Years whose originals the acquisition saved, read off the bytes its export
# carries against the results of the round that ran them.
CROSS_OLDER_YEARS = EVIDENCE + "cross-source-read-older-years.json"
CROSS_READINGS = (CROSS, CROSS_PARAMOUNT_PART_III, CROSS_OLDER_YEARS)
LODGING = EVIDENCE + "lodging-table-read.json"
# Marriott's older years, read off the export against the round that ran them.
LODGING_OLDER_YEARS = EVIDENCE + "lodging-table-read-older-years.json"
LODGING_READINGS = (LODGING, LODGING_OLDER_YEARS)
EVENTS = EVIDENCE + "event-count-read.json"
# Paramount's predecessor year, read the same way against the targeted Runs of
# the closure that cleared its event window (part-iii-statement-review/): a
# reading's positions all compare results of one closure, so it is its own file.
EVENTS_PARAMOUNT_PREDECESSOR = EVIDENCE + "event-count-read-paramount-2024.json"
EVENT_READINGS = (EVENTS, EVENTS_PARAMOUNT_PREDECESSOR)
# E01 counts an 8.01 only once a keyword in its text confirms it, which a count
# of header item codes cannot check. Every 8.01 in the E01 windows is read here
# by tools/read_e01_eight_o_ones.py, under each reading of that confirmation.
E01_EIGHT_O_ONES = EVIDENCE + "e01-eight-o-one-read.json"
# E01 under the owner's content-confirmed definition (a successor route with
# its own Spec): tools/read_e01_candidates.py reads each window's candidate
# items off their headers, and can accept only a window with none.
E01_CANDIDATES = EVIDENCE + "e01-content-confirmed-read.json"
# C02 under the owner's composition-fact meaning: the two-direction reading of
# c02-composition-facts/, compared with the published results by
# tools/read_c02_composition.py.
C02_COMPOSITION = EVIDENCE + "c02-composition-read.json"
GOVERNANCE = EVIDENCE + "governance-read.json"
# An older year's C03, read from every saved proxy that tags it (a year is
# reported again by each later proxy) by tools/read_c03_across_proxies.py; one
# file per closure its positions compare.
C03_ACROSS_PROXIES = (EVIDENCE + "c03-across-proxies-read-batch.json",
                      EVIDENCE + "c03-across-proxies-read-round3.json")
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
# Paramount's predecessor year, read off the predecessor's own 10-K (CIK 813828)
# against the result of the twelve-period batch.
HEADINGS_PARAMOUNT_PREDECESSOR = EVIDENCE + "d01-paramount-predecessor-2024-read.json"
# Years whose originals the acquisition saved, read off the bytes its export
# carries against the results of the round that ran them.
HEADINGS_OLDER_YEARS = EVIDENCE + "d01-older-years-read.json"
D01_READINGS = (HEADINGS, HEADINGS_FROM_BYTES, HEADINGS_PARAMOUNT_REPAIRED,
                HEADINGS_PARAMOUNT_PREDECESSOR, HEADINGS_OLDER_YEARS)
RPO = EVIDENCE + "rpo-read.json"
COMPENSATION = EVIDENCE + "paramount-compensation-table-read.json"
# B06 read off each filing's balance sheet and lease note by
# tools/read_debt_to_equity.py, which imports none of the debt cascade.
DEBT_TO_EQUITY = EVIDENCE + "debt-to-equity-read.json"
READINGS = (*CROSS_READINGS, *LODGING_READINGS, *EVENT_READINGS, E01_EIGHT_O_ONES, GOVERNANCE,
            TEXT, *D01_READINGS, RPO, COMPENSATION, DEBT_TO_EQUITY, C02_COMPOSITION,
            E01_CANDIDATES, *C03_ACROSS_PROXIES)
# The company periods the readings cover are data, not code: tools/ is scanned
# as production Python for identity literals and fixed dates.
POSITIONS = "docs/evidence/issue47_history/reading-producers/positions.json"
_POSITIONS = json.loads((Path(__file__).resolve().parent.parent / POSITIONS)
                        .read_text(encoding="utf-8"))
# The readings key some positions by a label only. The label is what the
# reading recorded, and this is the period each label names.
PERIODS = {label: row["report_end"] for label, row in _POSITIONS["labels"].items()}


def reading_cases(reading):
    """The (company_id, report_end, label) positions one reading covers, in its order."""
    return [(_POSITIONS["labels"][label]["company_id"], _POSITIONS["labels"][label]["report_end"],
             label) for label in _POSITIONS["readings"][reading]]
# What the acquisition saved travels in its export's archives, not extracted
# into the checkout. A member is the saved file's path under the exported data
# root, prefixed; the index records each member's digest.
EXPORT = "evidence/issue47_acquired"
EXPORT_MEMBER_PREFIX = "source-inputs/"
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


def _export_members(repo_root: Path):
    index = json.loads((repo_root / EXPORT / "export.json").read_text(encoding="utf-8"))
    members = {}
    for archive in index["row_archives"]:
        for path, meta in archive["members"].items():
            if path in members:
                raise ReadingError("READING_EXPORT_MEMBER_NOT_UNIQUE:" + path)
            members[path] = (archive["name"], meta["sha256"])
    return members


def _export_member_bytes(*, repo_root: Path, member: str, members):
    name, digest = members[member]
    with tarfile.open(repo_root / EXPORT / name) as archive:
        data = archive.extractfile(member).read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ReadingError("READING_EXPORT_MEMBER_DIGEST_DIFFERS:" + member)
    return data


def saved_bytes(*, repo_root: Path, relative: str):
    """A saved file's bytes: from the checkout, or else from the acquisition's export.

    A file the acquisition saved is carried by the export's archives rather
    than extracted into the checkout. It is taken by its exact path under the
    exported data root and checked against the digest the export's own index
    records, so a reading made over a restored root reads the same bytes here.
    """
    if (repo_root / relative).is_file():
        return (repo_root / relative).read_bytes()
    members = _export_members(repo_root)
    member = EXPORT_MEMBER_PREFIX + relative
    if member not in members:
        raise ReadingError("READING_FILE_NOT_SAVED:" + relative)
    return _export_member_bytes(repo_root=repo_root, member=member, members=members)


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
        if headers or (repo_root / relative).exists():
            if len(headers) != 1:
                raise ReadingError("READING_ATTEMPT_HEADERS_NOT_UNIQUE:" + document)
            saved = headers[0].read_bytes()
        else:
            # An attempt only the export carries: its headers travel with it.
            members = _export_members(repo_root)
            stem = EXPORT_MEMBER_PREFIX + str(relative) + "."
            named = [path for path in members
                     if path.startswith(stem) and path.endswith(".headers.json")
                     and "/" not in path[len(stem):]]
            if len(named) != 1:
                raise ReadingError("READING_ATTEMPT_HEADERS_NOT_UNIQUE:" + document)
            saved = _export_member_bytes(repo_root=repo_root, member=named[0], members=members)
        url = json.loads(saved.decode("utf-8"))["url"]
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
    if path in CROSS_READINGS:
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
    elif path in LODGING_READINGS:
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
    elif path in EVENT_READINGS:
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
    elif path in (E01_EIGHT_O_ONES, E01_CANDIDATES):
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
    elif path in C03_ACROSS_PROXIES:
        # The filings named are the ones the result names that the reading also
        # opened; the later proxies that confirm the value are the reading's
        # own, listed in the slot, and a binding cannot require the result to
        # name them.
        for label, case in sorted(body["per_position"].items()):
            found.append(_position(
                reading=path, label=label, slot=case, company_id=case["company_id"],
                metric_id="C03", period_end=case["period_end"], published=case["published"],
                verdict=case["verdict"], filings=case["opened_filings_the_result_names"],
                window=case["period"]))
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
    elif path == C02_COMPOSITION:
        # The value is the whole text payload, named by digest; the filing
        # named is the governance document whose blocks were judged.
        for label, case in sorted(body["per_position"].items()):
            found.append(_position(
                reading=path, label=label, slot=case, company_id=case["company_id"],
                metric_id="C02", period_end=case["period_end"],
                published=case["value_sha256"], verdict=case["verdict"],
                filings=[case["governance_accession"]]))
    elif path == DEBT_TO_EQUITY:
        for label, case in sorted(body["per_position"].items()):
            if case.get("published") is None:
                continue
            accession, _ = accession_of_document(repo_root=repo_root, document=case["document"])
            found.append(_position(
                reading=path, label=label, slot=case, company_id=case["company_id"],
                metric_id="B06", period_end=case["period_end"], published=case["published"],
                verdict=case["verdict"], filings=[accession]))
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
