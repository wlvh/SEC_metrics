"""B02 original revenue-scope admission using the existing public readers.

This module owns only the historical paired-income consumer. It introduces no
reader, Calculator or configuration bridge. Non-income cases do not consume it.
"""
from sec_urls import companyfacts_url
from .historical_dei import annual_period


def revenue_claims_admitted_by_original(*, reader, prepared, filing, period, claims, concepts,
                                       allow_single_revenue_line):
    """Use the shared source-total filter, retaining original claim identities."""
    from .historical_statement_cases import StatementCaseError, _need
    from .selected_revenue_scope_v1 import selected_revenue_scope, admit_revenue_facts
    from .selected_reported_revenue_v2 import reported_revenue_scope, admit_reported_revenue_facts
    from .xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
    from .historical_fiscal_labels import resolve_selected_fiscal_year_label
    from .canonical import sha256_bytes
    originals = reader.auditor_filing(filing)
    primary = next((s for s in originals if s['raw_blob']['media_type'] == 'text/html'), None)
    xml = next((s for s in originals if s['raw_blob']['media_type'] == 'application/xml'), None)
    _need(primary is not None, 'HISTORICAL_PAIRED_REVENUE_PRIMARY_REQUIRED', 'SOURCE_UNAVAILABLE')
    facts = reader.read(companyfacts_url(cik=int(prepared['entity'])),
        accession=filing['accessionNumber'], role='companyfacts', media_type='application/json')
    label = resolve_selected_fiscal_year_label(primary_bytes=primary['raw_bytes'],
        companyfacts_bytes=facts['raw_bytes'],
        expected_primary_sha256=sha256_bytes(content=primary['raw_bytes']),
        expected_companyfacts_sha256=sha256_bytes(content=facts['raw_bytes']),
        expected_cik=prepared['entity'], filing=filing)
    source_period = annual_period(raw=primary['raw_bytes'], cik=prepared['entity'], filing=filing)
    _need(all(source_period[key] == period[key] for key in ('period_start', 'period_end')),
          'HISTORICAL_PAIRED_REVENUE_ORIGINAL_PERIOD_CHANGED')
    annual = {'company_id': prepared['company_id'], 'entity': prepared['entity'],
        'filing': filing, 'table_input': {'target_period': source_period}}
    qualified = ['us-gaap:' + c.split(':')[-1] for c in concepts]
    scope = reported_revenue_scope(primary=primary, xml=xml, annual=annual,
        approved_concepts=qualified, namespace_policy=YEAR_OR_DATE_RELEASE,
        annual_period_reader=annual_period, fiscal_label_resolution=label,
        allow_single_revenue_line=allow_single_revenue_line)
    admit = admit_reported_revenue_facts
    if not scope['complete_scope_proven']:
        scope = selected_revenue_scope(primary=primary, xml=xml, annual=annual,
            approved_concepts=qualified, namespace_policy=YEAR_OR_DATE_RELEASE,
            annual_period_reader=annual_period)
        admit = admit_revenue_facts
    if not scope['complete_scope_proven']:
        raise StatementCaseError('HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN',
            'IMPLEMENTATION_GAP', revenue_scope=scope)
    views = []
    for claim in claims:
        _need(claim['claim_kind'] == 'COMPANYFACTS_NUMERIC_FACT'
              and ':' not in claim['locator']['concept'],
              'HISTORICAL_PAIRED_REVENUE_CLAIM_KIND_CHANGED')
        views.append({**claim['locator'], **claim['attributes'],
            'concept': 'us-gaap:' + claim['locator']['concept'],
            'value': claim['value'], 'unit': claim['unit'],
            'verified_claim_id': claim['verified_claim_id']})
    allowed = {v['verified_claim_id'] for v in admit(facts=views, scope=scope)}
    return [claim for claim in claims if claim['verified_claim_id'] in allowed], scope

