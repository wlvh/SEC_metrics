"""Thin saved-source declaration for the received ordinary history exporter.

Reuse the fiscal-range and annual dependency readers without changing their
processing identities for this export-only capability.
"""
from pathlib import Path
from sec_urls import accession_document_url, companyfacts_url
from .canonical import content_hash
from .company_fiscal_range import METRIC_IDS, _need, _issue, discover_fiscal_range
from .normal_source_authority import ROOT
from .normal_source_requirements import _Requirements
from .ordinary_registry_scope import registered_company_row
from .normal_history_catalog import annual_periods


def latest_history_source_frame(*, repo_root, company_id, years, metric_ids):
    """Name the received annual dependencies for the latest issuer-year window.

    This is a source declaration for export, not acquisition or calculation.
    Fiscal labels come from the latest original and the existing range reader;
    a report-end year, incomplete index or an unresolved year cannot substitute.
    """
    _need(years == 5 and type(years) is int, 'HISTORY_EXPORT_YEARS_INVALID')
    _need(type(metric_ids) in (tuple, list) and metric_ids and
          len(metric_ids) == len(set(metric_ids)) and set(metric_ids) <= METRIC_IDS,
          'HISTORY_EXPORT_METRIC_NOT_CONNECTED')
    source = Path(repo_root).resolve()
    company = registered_company_row(repo_root=source, company_id=company_id)
    _need(company == registered_company_row(repo_root=ROOT, company_id=company_id),
          'SOURCE_COMPANY_REGISTRY_CHANGED')
    from .normal_history_catalog import load_annual_history
    from .historical_fiscal_labels import resolve_selected_fiscal_year_label
    errors, selected, requirements = [], None, []
    try:
        history = load_annual_history(repo_root=source, company_id=company_id,
                                      required_annual_count=years + 1)
        _need(not history['limitations'], 'HISTORY_EXPORT_METADATA_INCOMPLETE')
        periods = annual_periods(history=history)
        _need(bool(periods) and periods[0]['original_status'] == 'SINGLE_ORIGINAL_ANNUAL',
              'HISTORY_EXPORT_LATEST_ORIGINAL_UNRESOLVED')
        filing = periods[0]['original']
        reader = _Requirements(source, company)
        primary = reader.require(accession_document_url(cik=int(company['primary_cik']),
            accession=filing['accessionNumber'], document_name=filing['primaryDocument']),
            'fiscal_label_primary', 'text/html', filing['accessionNumber'])
        facts = reader.require(companyfacts_url(cik=int(company['primary_cik'])),
                                'fiscal_label_companyfacts', 'application/json')
        _need(primary is not None and facts is not None, 'HISTORY_EXPORT_LABEL_SOURCE_MISSING')
        label = resolve_selected_fiscal_year_label(primary_bytes=primary['raw_bytes'],
            companyfacts_bytes=facts['raw_bytes'], expected_cik=company['primary_cik'], filing=filing,
            expected_primary_sha256=reader.requests[primary['source_reference']['source_url']]['proof']['content_sha256'],
            expected_companyfacts_sha256=reader.requests[facts['source_reference']['source_url']]['proof']['content_sha256'])
        last = label['selected_fiscal_year']
        selected = discover_fiscal_range(repo_root=source, company_id=company_id,
            fiscal_year_start=last-years+1, fiscal_year_end=last, metric_ids=metric_ids)
        seen = set()
        for task in selected['tasks']:
            for item in task.get('source_preflight', {}).get('requirements', []):
                if item['source_url'] not in seen:
                    requirements.append(item)
                    seen.add(item['source_url'])
        # The range reader also reads candidate labels to prove membership and
        # uniqueness. An older label can be needed even when B01 does not use
        # that older year's financial amounts; keep this selection dependency.
        for candidate in selected['candidates']:
            for name, media in (('primary_proof', 'text/html'),
                                ('companyfacts_proof', 'application/json')):
                proof = candidate.get(name)
                if proof is not None and proof['source_url'] not in seen:
                    requirements.append({'source_url': proof['source_url'], 'method': 'GET',
                        'roles': ['fiscal_label_candidate'], 'accession': proof['accession'],
                        'media_type': media, 'saved_status': 'VERIFIED_SAVED_SOURCE',
                        'source_acquisition_credit': False, 'proof': proof})
                    seen.add(proof['source_url'])
    except (ValueError, KeyError, TypeError) as error:
        errors.append(_issue('LATEST_HISTORY_SOURCE', error))
    complete = not errors and selected is not None and selected['status'] == 'FISCAL_RANGE_RESOLVED' \
        and selected['all_source_bytes_available']
    body = {'record_type': 'COMPANY_HISTORY_SOURCE_FRAME_V1', 'company_id': company_id,
        'metric_ids': list(metric_ids), 'requested_history_years': years,
        'fiscal_range': selected, 'requirements': requirements, 'limitations': errors,
        'status': 'SAVED_SOURCE_BYTES_AVAILABLE' if complete else 'SOURCE_EXPORT_INCOMPLETE',
        'discovery_scope': 'LATEST_FIVE_ISSUER_YEARS_SELECTED_ANNUAL_DEPENDENCIES',
        'calls': {'provider': 0, 'paid': 0, 'sec': 0}, 'fetch_authorized': False,
        'metric_executed': False, 'metric_acceptance_proven': False,
        'production_authorized': False}
    return {**body, 'frame_id': content_hash(value=body)}


