"""Read-only six-filing form-set check over exact saved Paramount sources."""
import argparse
import json
import re
from pathlib import Path

from sec_urls import accession_document_url, hdr_sgml_url, submissions_url
from vnext.canonical import sha256_bytes, strict_json_file
from vnext.continuous_call_ledger import live_ledger
from vnext.deterministic_router import (
    DeterministicRouterError, adapt_8k_item_index, source_set_manifest,
)
from vnext.normal_governance_input import _Sources
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


COMPANY = 'paramount_skydance_paramount_global'
FORMS = ['8-K', '8-K/A', '8-K12B', '8-K12B/A']


def run(root, prior_discovery):
    requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
    ledger = live_ledger(requirement=requirement)
    with ledger.locked():
        before = ledger.snapshot()
    discovery = strict_json_file(path=prior_discovery)['result']
    assert discovery['company_id'] == COMPANY and discovery['primary_cik'] == '2041610'
    selection = discovery['filing_selection']
    assert selection['history_loaded'] == []
    filings = sorted([*selection['events'], *selection['registration_event_filings']],
                     key=lambda row: (row['filingDate'], row['accessionNumber']))
    assert len(filings) == 6 and {row['form'] for row in filings} == {'8-K', '8-K12B', '8-K12B/A'}
    reader = _Sources(root, COMPANY, '2041610')
    inventory = reader.read(submissions_url(cik=2041610),
                            role='sec_submissions_inventory', media_type='application/json')
    prior_hash = strict_json_file(path=prior_discovery.parent/'four-url-plan.json')['metadata_raw_sha256']
    assert sha256_bytes(content=inventory['raw_bytes']) == prior_hash
    period = discovery['prepared_annual_input']['table_input']['target_period']
    window = {'period_start':period['period_start'], 'period_end':period['period_end']}
    docs, references, identities = [], [], []
    for filing in filings:
        accession = filing['accessionNumber']
        variant = filing['form'] in {'8-K12B', '8-K12B/A'}
        primary = reader.read(accession_document_url(cik=2041610, accession=accession,
            document_name=filing['primaryDocument']), accession=accession,
            role='registration_event_primary' if variant else 'fy_8k_primary', media_type='text/html')
        header = reader.read(hdr_sgml_url(cik=2041610, accession=accession),
            accession=accession, role='registration_event_header' if variant else 'fy_8k_header',
            media_type='text/plain')
        match = re.search(rb'<TYPE>\s*([^\r\n]+)', header['raw_bytes'], re.I)
        assert match is not None and match.group(1).decode('ascii').strip() == filing['form']
        docs.append({'hdr_bytes':header['raw_bytes'],
                     'hdr_source_reference':header['source_reference'],
                     'primary_document_bytes':primary['raw_bytes'],
                     'primary_source_reference':primary['source_reference']})
        references.extend([header['source_reference'], primary['source_reference']])
        identities.append({'form':filing['form'], 'accession':accession,
                           'header_sha256':sha256_bytes(content=header['raw_bytes']),
                           'primary_sha256':sha256_bytes(content=primary['raw_bytes']),
                           'header_attempt_id':header['source_reference']['request_attempt_id'],
                           'primary_attempt_id':primary['source_reference']['request_attempt_id']})
    manifest = source_set_manifest(company_id=COMPANY, source_role='fy_8k_item_inventory',
        form_types=FORMS, fiscal_or_date_window=window, discovery_policy='PINNED_SUBMISSIONS',
        inventory_source_reference=inventory['source_reference'], inventory_bytes=inventory['raw_bytes'],
        ordered_source_references=references,
        cutoff_timestamp_or_pinned_submissions_attempt=inventory['source_reference']['request_attempt_id'])
    claims = adapt_8k_item_index(filing_documents=docs, source_set_manifest=manifest,
        inventory_source_reference=inventory['source_reference'], inventory_bytes=inventory['raw_bytes'])
    try:
        adapt_8k_item_index(filing_documents=docs[:-1], source_set_manifest=manifest,
            inventory_source_reference=inventory['source_reference'], inventory_bytes=inventory['raw_bytes'])
    except DeterministicRouterError:
        omitted_filing_rejected = True
    else:
        raise AssertionError('C04_SAVED_FORM_OMISSION_WAS_ACCEPTED')
    try:
        source_set_manifest(company_id=COMPANY, source_role='fy_8k_item_inventory',
            form_types=['8-K', '8-K/A'], fiscal_or_date_window=window,
            discovery_policy='PINNED_SUBMISSIONS',
            inventory_source_reference=inventory['source_reference'],
            inventory_bytes=inventory['raw_bytes'], ordered_source_references=references,
            cutoff_timestamp_or_pinned_submissions_attempt=inventory['source_reference']['request_attempt_id'])
    except DeterministicRouterError:
        old_form_set_rejected = True
    else:
        raise AssertionError('C04_OLD_FORM_SET_ACCEPTED_EXTRA_FILINGS')
    by_accession = {filing['accessionNumber']:sorted({claim['attributes']['item_code']
        for claim in claims if claim['attributes']['accession']==filing['accessionNumber']})
        for filing in filings}
    with ledger.locked():
        after = ledger.snapshot()
    assert after['counts'] == before['counts'] and len(after['rows']) == len(before['rows'])
    return {'record_type':'ISSUE28_PARAMOUNT_C04_SAVED_FORM_ACCEPTANCE_PROBE',
            'source_root':str(root), 'inventory_sha256':prior_hash,
            'forms':FORMS, 'filings':identities,
            'source_set_manifest_id':manifest['source_set_manifest_id'],
            'item_claim_count':len(claims),
            'item_4_01_claim_count':sum(row['attributes']['item_code']=='4.01' for row in claims),
            'item_codes_by_accession':by_accession,
            'claim_accessions':sorted({row['attributes']['accession'] for row in claims}),
            'form_set_complete_for_saved_inventory':True,
            'header_forms_match_submissions':True,
            'omitted_filing_rejected':omitted_filing_rejected,
            'old_form_set_with_variant_filings_rejected':old_form_set_rejected,
            'old_c04_v2_form_set_changed':False,
            'registrant_auditor_comparison_complete':False,
            'metric_result_created':False,
            'new_calls':[0,0,0], 'ledger_counts_unchanged':before['counts']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger-root', type=Path, required=True)
    parser.add_argument('--discovery', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.ledger_root/'source-inputs', args.discovery)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key:result[key] for key in ('item_claim_count','item_4_01_claim_count',
        'source_set_manifest_id','new_calls','ledger_counts_unchanged')}))
