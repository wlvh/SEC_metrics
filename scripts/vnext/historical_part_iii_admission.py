"""Per-filing admission of a Part III amendment's period for statement values.

Purpose:
    The approved amendment policy clears a Part III addition's event window
    and not its statement values, and says the latter needs further review.
    That review was done filing by filing
    (``docs/evidence/issue47_history/part-iii-statement-review/``) and the
    owner decided on it: the two amendments named in
    ``config/issue47_part_iii_statement_admission_v1.json`` may clear
    ``ORIGINAL_STATEMENT_VALUES`` for their own periods, for the metrics the
    review measured as refused, on the evidence the review recorded.

    So this is not a rule about Part III amendments. An amendment that is not
    listed by accession gets exactly the approved policy's answer, as before.
    A listed one is admitted only when its evidence still holds, read again
    from the saved bytes every time: the bytes are the ones reviewed; its note
    reads, sentence by sentence, as the approved Part III class naming the
    original's year end and filing date; it contains Part III and Part IV
    only; it declares that no financial statements are filed with it; its
    native facts are governance taxonomy only; its fiscal window is the
    original's; and its Item 15 files the certifications and the XBRL and
    cover-page files and nothing else. Any condition that fails is named, and
    only that amendment's positions stay refused.

    The target stays the original filing. Nothing here reads a value from an
    amendment or joins one registrant's figures to another's: each entry is
    one registrant's own period, and the metrics it lists are that period's.

Call relationships:
    ``historical_amendment_admission`` calls this for an amendment the policy
    left uncleared for statement values. It creates no Run, no Result and no
    acquisition.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .canonical import content_hash, sha256_bytes
from .normal_annual_input_v2 import exact_json_value

CONFIG_PATH = "config/issue47_part_iii_statement_admission_v1.json"
RECORD_TYPE = "ISSUE_47_PART_III_STATEMENT_VALUES_ADMISSION"
REFUSAL_READ_AS = "AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN"
_EXHIBIT = re.compile(r"^\((\d+)\)", re.M)


class PartIIIAdmissionError(ValueError):
    """The per-filing admission record itself cannot be read as approved."""


def _need(condition, reason):
    if not condition:
        raise PartIIIAdmissionError(reason)


def approved_filings(*, repo_root: Path, input_class: str) -> list:
    """The listed filings, after the record is checked to say what it must."""
    record = json.loads((Path(repo_root) / CONFIG_PATH).read_text(encoding="utf-8"))
    _need(record.get("record_type") == RECORD_TYPE and record.get("schema_version") == 1
          and record.get("requirement_id") == "issue_47_v1"
          and record.get("production_authorized") is False,
          "PART_III_ADMISSION_RECORD_INVALID")
    _need(record.get("input_class") == input_class,
          "PART_III_ADMISSION_IS_FOR_ANOTHER_INPUT_CLASS:" + str(record.get("input_class")))
    filings = record.get("filings")
    _need(type(filings) is list and filings, "PART_III_ADMISSION_LISTS_NO_FILING")
    seen = set()
    for entry in filings:
        accession = entry["amendment"]["accession"]
        _need(accession not in seen, "PART_III_ADMISSION_FILING_LISTED_TWICE:" + accession)
        seen.add(accession)
        _need(type(entry["metrics"]) is list and entry["metrics"]
              and len(set(entry["metrics"])) == len(entry["metrics"]),
              "PART_III_ADMISSION_METRICS_INVALID:" + accession)
        _need(re.fullmatch(r"[0-9a-f]{64}", entry["amendment"]["content_sha256"]) is not None,
              "PART_III_ADMISSION_DIGEST_INVALID:" + accession)
    return [{**entry, "exhibits_allowed": sorted(record["exhibits_allowed"])}
            for entry in filings]


def _entry(*, repo_root, input_class, company_id, cik, original, amendment):
    """The listed entry for exactly this amendment of exactly this original, or None."""
    for entry in approved_filings(repo_root=repo_root, input_class=input_class):
        if entry["amendment"]["accession"] != amendment["filing"]["accessionNumber"]:
            continue
        # Listed by accession, so everything else about it must agree: a
        # listing is for one registrant's one period and one original.
        _need(entry["company_id"] == company_id
              and str(entry["registrant_cik"]) == str(int(cik))
              and entry["report_end"] == original["filing"]["reportDate"]
              and entry["original"]["accession"] == original["filing"]["accessionNumber"]
              and entry["original"]["document"] == original["filing"]["primaryDocument"]
              and entry["amendment"]["document"] == amendment["filing"]["primaryDocument"],
              "PART_III_ADMISSION_LISTING_DOES_NOT_MATCH_THE_FILING:"
              + amendment["filing"]["accessionNumber"])
        return entry
    return None


def statement_values_admission(*, repo_root: Path, input_class: str, company_id: str, cik,
                               original: dict, amendment: dict, metric_ids) -> dict | None:
    """Whether this listed amendment clears ``input_class`` for ``metric_ids``.

    Args:
        repo_root: Data root holding the rule inputs.
        input_class: The class the metrics need; only the listed one is admitted.
        company_id: Logical company.
        cik: The registrant whose original and amendment these are.
        original: The original annual filing's saved source, as the caller read it.
        amendment: The amendment's saved source, as the caller read it.
        metric_ids: The metrics the caller resolves together.

    Returns:
        None when the amendment is not listed. Otherwise a record of every
        condition checked and whether all held, with the failures named.
    """
    from .annual_amendment_scope import _item15, _source
    from .historical_amendment_note import AmendmentNoteError, read_part_iii_note
    entry = _entry(repo_root=repo_root, input_class=input_class, company_id=company_id,
                   cik=cik, original=original, amendment=amendment)
    if entry is None:
        return None
    outside = sorted(set(metric_ids) - set(entry["metrics"]))
    conditions = {"METRICS_WITHIN_THE_APPROVED_SCOPE": not outside,
                  "AMENDMENT_BYTES_ARE_THE_REVIEWED_ONES":
                      sha256_bytes(content=amendment["raw"])
                      == entry["amendment"]["content_sha256"]}
    note_refusal, exhibits = None, None
    try:
        note = read_part_iii_note(original=original, amendment=amendment,
                                  company_id=company_id, cik=cik, refusal=REFUSAL_READ_AS)
    except AmendmentNoteError as error:
        note, note_refusal = None, str(error)
    # The note reader proves the pointer to the original, every sentence's
    # kind, Part III and Part IV only, the one no-financial-statement
    # declaration, governance-only native facts and the unchanged fiscal
    # window, and raises on the first that fails.
    conditions["NOTE_READS_AS_THE_APPROVED_PART_III_CLASS"] = note is not None
    source = _source(**amendment, company_id=company_id, cik=cik,
                     period_end=original["filing"]["reportDate"])
    lines = [block["text"] for block in _item15(source["document"])["blocks"]]
    exhibits = sorted(set(_EXHIBIT.findall("\n".join(lines))))
    conditions["ITEM_15_FILES_ONLY_CERTIFICATIONS_AND_INTERACTIVE_DATA"] = (
        exhibits == entry["exhibits_allowed"])
    failed = sorted(name for name, held in conditions.items() if not held)
    body = exact_json_value({
        "record_type": "HISTORICAL_PART_III_STATEMENT_ADMISSION", "schema_version": 1,
        "input_class": input_class, "company_id": company_id,
        "amendment_accession": amendment["filing"]["accessionNumber"],
        "original_accession": original["filing"]["accessionNumber"],
        "report_end": original["filing"]["reportDate"],
        "metric_ids": sorted(set(metric_ids)), "metrics_outside_the_approved_scope": outside,
        "conditions": conditions, "failed": failed, "note_refusal": note_refusal,
        "item_15_exhibits": exhibits,
        "note_scope_id": note["scope_id"] if note is not None else None,
        "admitted": not failed, "production_authorized": False})
    return {**body, "admission_id": content_hash(value=body)}
