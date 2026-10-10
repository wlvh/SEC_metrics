"""Locate an explicit visible audit-report candidate, without C04 result credit.

The structured-only C04 contract is unchanged. This development adapter keeps
the auditee, opinion period and report signature together in original bytes;
it does not manufacture a native AuditorName fact or a no-change conclusion.
"""
from __future__ import annotations

from datetime import datetime
import re

from .canonical import content_hash, sha256_bytes
from .deterministic_router import parse_accession_xbrl_source
from .governance_signals import _FactAttributes
from .normal_annual_input import dei_namespace_pattern
from .text_coverage import build_text_document


_HEADING = re.compile(r"Report of Independent Registered Public Accounting Firm", re.I)
_CLOSE = re.compile(r"(?:consolidated (?:statements? of|balance sheets)|signatures|item\s+(?:9|9A|15)\b)", re.I)
_DATE = re.compile(r"([A-Za-z]+\s+\d{1,2},\s+\d{4})")


def _normal(value):
    # A lexical corporate abbreviation is recorded, not a subject change.
    return re.sub(r"\bco\.?$", "company", " ".join(value.split()).casefold())


def _registered_name(raw, *, cik, period_end):
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    attributes = _FactAttributes()
    attributes.feed(raw.decode("utf-8-sig"))
    attributes.close()
    names = set()
    for fact in parsed.facts:
        uri, local = attributes.facts[fact["ordinal"]]["concept"]
        if (re.fullmatch(dei_namespace_pattern("YEAR_QUARTER_OR_DATE"), uri)
                and local.casefold() == "entityregistrantname"):
            context = parsed.contexts[fact["context_ref"]]
            if (context["dimensions"] or context["typed_dimension_count"]
                    or not str(context["entity_identifier"]).isdigit()
                    or int(context["entity_identifier"]) != int(cik)
                    or context["period_end"] != period_end):
                return None
            names.add(" ".join(fact["text"].split()))
    return next(iter(names)) if len(names) == 1 else None


def _locator(block):
    return {key: block[key] for key in (
        "block_index", "text", "raw_start_byte", "raw_end_byte", "raw_span_sha256")}


def _cover_charter_name(document):
    """Use the explicit cover label, not a stripped native-name suffix."""
    blocks = document["blocks"]
    end = next((i for i, b in enumerate(blocks) if
        re.match(r"(?:item\s+\d|part\s+[IVX]+\b)", b["text"], re.I)
        or _HEADING.fullmatch(b["text"])), len(blocks))
    cover = blocks[:end]
    forms = [i for i, b in enumerate(cover) if not b["linked"] and
        re.fullmatch(r"FORM\s+" + re.escape(document["form"]), b["text"], re.I)]
    commission = [i for i, b in enumerate(cover) if not b["linked"] and
        b["text"].upper() == "SECURITIES AND EXCHANGE COMMISSION"]
    pairs = []
    if len(forms) == 1 and len(commission) == 1 and commission[0] < forms[0]:
        for i, b in enumerate(cover):
            if i > forms[0] + 1 and not b["linked"] and re.fullmatch(
                    r"\(Exact name of registrant as specified in its charter\)",
                    b["text"], re.I) and not cover[i - 1]["linked"]:
                pairs.append({"name": cover[i - 1]["text"],
                    "name_locator": _locator(cover[i - 1]),
                    "label_locator": _locator(b),
                    "form_locator": _locator(cover[forms[0]]),
                    "commission_locator": _locator(cover[commission[0]])})
    return {"status": "LOCATED" if len(pairs) == 1 else "UNRESOLVED",
            "candidates": pairs}


def inspect_visible_auditor_report(*, raw_bytes, raw_blob, source_reference,
                                 expected_company_id, expected_cik,
                                 expected_period_end,
                                 registrant_binding="NATIVE_NAME_ONLY"):
    """Inspect a finite standard report layout; unsupported cases stay unresolved.

    This source-only entry uses exact SEC document labels. It does not accept
    old local filename aliases: their capture proof needs its explicit adapter.
    No completeness of all audit reports/filing events is inferred from a hit.
    """
    if registrant_binding not in {"NATIVE_NAME_ONLY", "COVER_CHARTER_NAME"}:
        raise ValueError("VISIBLE_AUDITOR_REGISTRANT_BINDING_INVALID")
    document = build_text_document(raw_bytes=raw_bytes, raw_blob=raw_blob,
        source_reference=source_reference, expected_company_id=expected_company_id,
        expected_cik=expected_cik, expected_period_end=expected_period_end,
        dei_release="YEAR_QUARTER_OR_DATE")
    blocks = document["blocks"]
    name = _registered_name(raw_bytes, cik=expected_cik,
                            period_end=expected_period_end)
    reasons = list(document["source_reasons"])
    if name is None:
        reasons.append("VISIBLE_AUDITOR_REGISTRANT_NAME_NOT_UNIQUE")
    cover = _cover_charter_name(document) if registrant_binding == "COVER_CHARTER_NAME" else None
    report_name = name
    if cover is not None:
        if cover["status"] == "LOCATED":
            report_name = cover["candidates"][0]["name"]
        else:
            reasons.append("VISIBLE_AUDITOR_COVER_CHARTER_NAME_NOT_UNIQUE")
    headings = [i for i, b in enumerate(blocks)
                if not b["linked"] and _HEADING.fullmatch(b["text"])]
    reports = []
    for ordinal, start in enumerate(headings):
        end = headings[ordinal + 1] if ordinal + 1 < len(headings) else len(blocks)
        # Stop at actual statement/section headings, never attach a signature
        # from another section. A long prose opinion is not a closing heading.
        end = next((i for i in range(start + 1, end)
                    if _CLOSE.match(blocks[i]["text"]) and
                    len(blocks[i]["text"]) <= 100), end)
        scope = blocks[start + 1:end]
        # A contents entry lacks an auditee/opinion and is not a report.
        if not any(re.match(r"To the\s", b["text"], re.I) for b in scope):
            continue
        problems = []
        purpose = ("INTERNAL_CONTROL_REPORT" if any(re.fullmatch(
            r"Opinion on Internal Control over Financial Reporting", b["text"], re.I)
            for b in scope) else "FINANCIAL_STATEMENT_REPORT")
        addresses = [b for b in scope if re.fullmatch(
            r"To the (?:Board of Directors and (?:Stockholders|Shareholders)|"
            r"(?:Stockholders|Shareholders) and Board of Directors) of\s+.+",
            b["text"], re.I)]
        if len(addresses) != 1 or report_name is None or not _normal(addresses[0]["text"]).endswith(
                " of " + _normal(report_name)):
            problems.append("VISIBLE_AUDITOR_AUDITEE_NOT_ESTABLISHED")
        opinions = [b for b in scope if re.match(
            r"We have audited the (?:accompanying )?consolidated balance sheets? of\s+",
            b["text"], re.I)]
        if len(opinions) != 1:
            problems.append("VISIBLE_AUDITOR_FINANCIAL_OPINION_NOT_ESTABLISHED")
        else:
            opinion = opinions[0]["text"]
            subject = re.match(r"We have audited the (?:accompanying )?consolidated balance sheets? of\s+(.+?)\s+as of\s+",
                               opinion, re.I)
            subject_ok = subject and report_name and _normal(subject[1]) in {
                _normal(report_name), _normal(report_name) + " and its subsidiaries",
                _normal(report_name) + " (the company)",
                _normal(report_name) + " (the “company”)",
                _normal(report_name) + ' (the "company")',
                _normal(report_name) + " and its subsidiaries (the “company”)",
                _normal(report_name) + ' and its subsidiaries (the "company")'}
            if not subject_ok:
                problems.append("VISIBLE_AUDITOR_OPINION_SUBJECT_NOT_ESTABLISHED")
            first_date = _DATE.search(opinion[subject.end():] if subject else "")
            try:
                opinion_end = datetime.strptime(first_date[1], "%B %d, %Y").date().isoformat() if first_date else None
            except ValueError:
                opinion_end = None
            if opinion_end != expected_period_end:
                problems.append("VISIBLE_AUDITOR_OPINION_PERIOD_NOT_ESTABLISHED")
        signatures = [b for b in scope if re.fullmatch(r"/s/\s+[^/]+", b["text"], re.I)]
        if len(signatures) != 1:
            problems.append("VISIBLE_AUDITOR_REPORT_SIGNATURE_NOT_UNIQUE")
        elif opinions and signatures[0]["block_index"] <= opinions[0]["block_index"]:
            problems.append("VISIBLE_AUDITOR_SIGNATURE_BEFORE_OPINION")
        dates = []
        if len(signatures) == 1:
            for b in scope:
                if b["block_index"] <= signatures[0]["block_index"]:
                    continue
                match = _DATE.fullmatch(b["text"])
                if match:
                    try:
                        dates.append((datetime.strptime(match[1], "%B %d, %Y").date().isoformat(), b))
                    except ValueError:
                        pass
        if len(dates) != 1 or dates[0][0] < expected_period_end:
            problems.append("VISIBLE_AUDITOR_REPORT_DATE_NOT_ESTABLISHED")
        spans = [blocks[start], *scope]
        report = {"status": "UNRESOLVED" if problems else "BOUND_REPORT_CANDIDATE",
            "report_purpose": purpose,
            "reasons": sorted(set(problems)), "heading": _locator(blocks[start]),
            "auditee": [_locator(b) for b in addresses],
            "opinions": [_locator(b) for b in opinions],
            "signatures": [_locator(b) for b in signatures],
            "report_dates": [{"date": d, **_locator(b)} for d, b in dates],
            "raw_start_byte": spans[0]["raw_start_byte"],
            "raw_end_byte": spans[-1]["raw_end_byte"]}
        report["raw_span_sha256"] = sha256_bytes(content=raw_bytes[
            report["raw_start_byte"]:report["raw_end_byte"]])
        reports.append(report)
    financial = [r for r in reports if r["report_purpose"] == "FINANCIAL_STATEMENT_REPORT"]
    if len(financial) != 1 or any(r["reasons"] for r in financial):
        reasons.append("VISIBLE_AUDITOR_REPORT_NOT_UNIQUE_OR_UNRESOLVED")
    result = {"record_type": "VISIBLE_AUDITOR_SOURCE_INSPECTION", "version": "1",
        "source_reference": document["source_reference"],
        "raw_asset_id": document["raw_asset_id"], "company_id": expected_company_id,
        "cik": document["cik"], "period_end": expected_period_end,
        "registrant_name": name, "reports": reports,
        "status": "UNRESOLVED" if reasons else "BOUND_REPORT_CANDIDATE",
        "reasons": sorted(set(reasons)), "native_fact_credit": False,
        "metric_result_credit": False, "publication_credit": False}
    if cover is not None:
        result.update(version="2", registrant_binding=registrant_binding,
                      cover_charter_name=cover, report_registrant_name=report_name)
    result["inspection_id"] = content_hash(value=result)
    return result


def verify_visible_auditor_report(*, inspection, **source_arguments):
    rebuilt = inspect_visible_auditor_report(**source_arguments)
    if rebuilt != inspection:
        raise ValueError("VISIBLE_AUDITOR_SOURCE_REPLAY_MISMATCH")
    return rebuilt
