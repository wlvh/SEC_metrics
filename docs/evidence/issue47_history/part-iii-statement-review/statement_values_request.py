"""The evidence a statement-values decision on the two Part III amendments rests on.

The approved policy clears a Part III amendment's event window and does not
clear its statement values; it sets original_statement_admission_requires_
further_review. The absence of financial tags alone does not prove nothing
else changed, so for each saved Part III amendment this records, from the
filing's own bytes: the report it says it amends, every sentence of its
explanatory note, what the amendment contains (Parts and Items), what it
files (its Item 15 exhibit list), and its native facts. It then measures which
coordinates are refused today for want of the statement-values clearance, by
running the routes, so the request cites the current scope rather than an
earlier count. Nothing is decided and no policy file is changed. Zero calls.

Usage, from the repository root:
    python3 docs/evidence/issue47_history/part-iii-statement-review/statement_values_request.py
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
from sec_urls import accession_document_url  # noqa: E402
from vnext.annual_amendment_scope import (AmendmentScopeError, _item15, _source,  # noqa: E402
                                          inspect_annual_amendment_scope)
from vnext.annual_update import saved_source  # noqa: E402
from vnext.historical_amendment_note import read_part_iii_note  # noqa: E402
from vnext.historical_annual_input import prepare_historical_annual_input  # noqa: E402
from vnext.historical_results import resolve_historical_companyfacts_metrics  # noqa: E402
from vnext.historical_zero_ai_results import resolve_historical_zero_ai_metric  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402
from vnext.sources import raw_blob_record, source_reference_record  # noqa: E402

COMPANY = "paramount_skydance_paramount_global"
PERIODS = ("2024-12-31", "2025-12-31")
REFUSED = "HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED"
HERE = Path(__file__).resolve().parent


def _read(prepared, filing):
    url = accession_document_url(cik=int(prepared["entity"]), accession=filing["accessionNumber"],
                                 document_name=filing["primaryDocument"])
    saved = saved_source(repo_root=REPO, url=url, accession=filing["accessionNumber"])
    proof = saved["proof"]
    blob = raw_blob_record(repo_root=REPO, repo_relative_path=proof["request_repo_relative_path"],
                           media_type="text/html")
    reference = source_reference_record(
        raw_blob=blob, company_id=COMPANY, source_url=url, accession=filing["accessionNumber"],
        document_name=filing["primaryDocument"], source_role="annual_source_identity",
        request_attempt_id=proof["request_attempt_id"])
    return {"raw": saved["raw"], "blob": blob, "reference": reference, "filing": filing}


def _amendment(period_end):
    selection = resolve_period_selection(repo_root=REPO, company_id=COMPANY, report_end=period_end)
    prepared = prepare_historical_annual_input(repo_root=REPO, company_id=COMPANY,
                                               period_selection=selection)
    (filing,) = prepared["amendments"]
    original, amendment = _read(prepared, prepared["filing"]), _read(prepared, filing)
    try:
        frozen = inspect_annual_amendment_scope(original=original, amendment=amendment,
                                                company_id=COMPANY, cik=prepared["entity"])
        classifier = {"classification": frozen["classification"], "issues": frozen["issues"]}
        refusal = "AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN"
    except AmendmentScopeError as error:
        classifier = {"refused": str(error)}
        refusal = str(error)
    note = read_part_iii_note(original=original, amendment=amendment, company_id=COMPANY,
                              cik=prepared["entity"], refusal=refusal)
    source = _source(**amendment, company_id=COMPANY, cik=prepared["entity"], period_end=period_end)
    exhibits = [block["text"] for block in _item15(source["document"])["blocks"]]
    concepts = sorted({"/".join(fact["concept"]) for fact in source["non_dei_native_facts"]})
    return selection, {
        "accession": filing["accessionNumber"], "document": filing["primaryDocument"],
        "filed": filing["filingDate"],
        "amends": {"accession": prepared["filing"]["accessionNumber"],
                   "document": prepared["filing"]["primaryDocument"],
                   "filed": prepared["filing"]["filingDate"], "report_end": period_end,
                   "the_note_names_it": note["pointer"]},
        "approved_classifier": classifier,
        "whole_note": [{"kind": row["kind"], "sentence": row["sentence"]}
                       for row in note["note"]["sentences"]],
        "content": {"parts": note["details"]["parts"], "items": note["details"]["items"]},
        "exhibits_filed": {"item_15_lines": exhibits,
                           "exhibit_numbers": sorted(set(re.findall(r"^\((\d+)\)", "\n".join(
                               exhibits), re.M)))},
        "no_financial_statement_declaration": note["details"][
            "no_new_financial_statement_declarations"],
        "native_facts": {"non_dei": len(source["non_dei_native_facts"]),
                         "all_in_the_governance_taxonomy":
                             note["details"]["non_dei_facts_are_governance_taxonomy"],
                         "concepts": concepts}}


def _refused_for_statement_values(selection):
    refused = {}
    facts = resolve_historical_companyfacts_metrics(repo_root=REPO, company_id=COMPANY,
                                                    period_selection=selection)
    for metric, row in sorted(facts["metrics"].items()):
        decision = (row.get("selection") or {}).get("amendment_policy_decision") or ""
        if row["result"]["reason_code"] == REFUSED and "ORIGINAL_STATEMENT_VALUES" in decision:
            refused[metric] = "companyfacts"
    for metric in ("B01", "B03"):
        component = resolve_historical_zero_ai_metric(repo_root=REPO, company_id=COMPANY,
                                                      metric_id=metric, period_selection=selection)
        decision = component["input_binding"]["selection"].get("amendment_policy_decision") or ""
        if component["result"]["reason_code"] == REFUSED and "ORIGINAL_STATEMENT_VALUES" in decision:
            refused[metric] = "zero_ai"
    return refused


def main():
    amendments, scope = {}, {}
    for period_end in PERIODS:
        selection, amendments[period_end] = _amendment(period_end)
        scope[period_end] = _refused_for_statement_values(selection)
        print(period_end, sorted(scope[period_end]), flush=True)
    report = {
        "record_type": "ISSUE_47_PART_III_STATEMENT_VALUES_REQUEST",
        "status": "EVIDENCE_FOR_A_DECISION_NOT_TAKEN",
        "what_is_asked": ("whether each of these two Part III amendments may clear "
                          "ORIGINAL_STATEMENT_VALUES for its own period, on the evidence below, "
                          "per amendment - not a rule that clears every future Part III "
                          "amendment on two mechanical conditions"),
        "amendments": amendments,
        "current_scope": {period: {"coordinates": len(rows), "metrics": sorted(rows)}
                          for period, rows in scope.items()},
        "supersedes": ("finding.json's '13 coordinates' and 'one positive': five of those "
                       "thirteen now answer structurally and two (B01, B03) through the "
                       "approved successor income input; second-instance.json's refusal of "
                       "the predecessor's note is repaired as markup (historical_amendment_note)"),
        "what_the_evidence_shows": [
            "each note names the report it amends, and the named year end and filing date are the original's",
            "every sentence of each note is the purpose, the approved no-change statement or a defined-terms sentence",
            "each amendment contains Part III (Items 10-14) and Part IV (Item 15) only",
            "each files only Rule 13a-14(a) certifications and the XBRL and cover-page files - no financial statement, no Section 906 certification",
            "each declares 'No financial statements or supplemental data are filed with this Amendment.'",
            "each carries native facts from the governance taxonomy only"],
        "what_it_does_not_show": [
            "that Part III content cannot bear on how a statement value is read: Item 13 related-party "
            "transactions and Item 10 independence are why B06, B13, C02-C04 and D01-D04 stay refused "
            "whatever is decided here",
            "anything about another Part III amendment: the evidence is per filing, and a filing that "
            "restates, files a statement exhibit or adds a purpose sentence would fail it"],
        "production_authorized": False, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    (HERE / "statement-values-request.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
