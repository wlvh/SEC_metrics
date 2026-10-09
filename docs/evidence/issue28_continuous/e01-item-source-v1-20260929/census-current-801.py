"""Bounded current-source census of ten-company 8.01 claims, not E01 credit."""
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.e01_item_source import bound_801_primary_section
from vnext.normal_annual_input import _registry_rows
from vnext.normal_run_v3 import prepare_case
from vnext.ordinary_processing_source import verify_processing_source
from vnext.requirements import load_requirement_snapshot
from vnext.sources import resolve_repository_file


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
processing = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'b03-ford-exact-repair-20260929/processing.json').read_text())
source = Path(processing['processing_root'])
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
verified = verify_processing_source(
    acquisition_root=ACQUIRED/'source-inputs', processing_root=source,
    requirement=requirement)
assert verified['snapshot_id'] == processing['source_snapshot_id']
policy = json.loads((ROOT/'catalog/event_routes.json').read_text())
rules = policy['routes']['E01']['keyword_item_rules']
assert len(rules) == 1 and rules[0]['item_code'] == '8.01'
aliases = rules[0]['aliases']
companies = [row['company_id'] for row in _registry_rows(repo_root=ROOT)]
assert len(companies) == len(set(companies)) == 10
rows = []
for company_id in companies:
    case = prepare_case(data_root=source, company_id=company_id,
                        metric_id='E01')
    assert case['admission']['source_credit'] in {
        'VERIFIED_SEC_ACQUISITION', 'PREEXISTING_SAVED_ACQUISITIONS_ONLY'}
    component = case['input_binding']['component']
    claims = component['claims']
    references = {ref['source_reference_id']: ref for ref in case['references']}
    blobs = {blob['raw_asset_id']: blob for blob in case['source_records']
             if blob['record_type'] == 'RAW_BLOB'}
    eight = [claim for claim in claims
             if claim['attributes'].get('item_code') == '8.01']
    inspected = []
    for claim in eight:
        ref = references[claim['attributes']['primary_source_reference_id']]
        blob = blobs[ref['raw_asset_id']]
        raw = resolve_repository_file(repo_root=source,
            repo_relative_path=blob['storage_uri']).read_bytes()
        assert ref['raw_asset_id'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
        item = {'accession': claim['attributes']['accession'],
            'verified_claim_id': claim['verified_claim_id'],
            'primary_source_reference_id': ref['source_reference_id'],
            'primary_raw_asset_id': ref['raw_asset_id'],
            'brief_source': claim['attributes']['brief_source'],
            'counted_under_current_rule': claim['verified_claim_id'] in
                component['selection'].get('matched_verified_claim_ids', [])}
        try:
            section = bound_801_primary_section(claim=claim,
                primary_source_reference=ref, primary_document_bytes=raw)
        except ValueError as error:
            item.update(section_status='REJECTED', reason=str(error),
                        keyword_hits_unverified=[])
        else:
            text = ' '.join(unicodedata.normalize('NFKC',
                section['section_text']).casefold().split())
            hits = [alias for alias in aliases if alias.casefold() in text]
            contexts = []
            for alias in hits:
                match = re.search(re.escape(alias.casefold()), text)
                contexts.append({'alias': alias,
                    'context': text[max(0, match.start()-80):match.end()+100]})
            item.update(section_status='BOUND_VISIBLE_SECTION',
                section_id=section['section_id'],
                section_text_sha256=section['section_text_sha256'],
                section_chars=len(section['section_text']),
                keyword_hits_unverified=contexts)
        inspected.append(item)
    rows.append({'company_id': company_id,
        'current_e01_result_id': case['results']['E01']['result_id'],
        'current_e01_publication': case['results']['E01']['publication'],
        'current_e01_reason': case['results']['E01']['reason_code'],
        'current_e01_value': case['results']['E01']['value'],
        'source_credit': case['admission']['source_credit'],
        'source_selection': component['selection'],
        'verified_claim_count': len(claims),
        'item_801_claims': inspected})
    print(company_id, len(eight), flush=True)
assert before == {key: digest(path) for key, path in originals.items()}
body = {'record_type': 'ISSUE28_E01_TEN_COMPANY_CURRENT_801_SOURCE_CENSUS',
    'scope': 'CURRENT_REGISTERED_SOURCE_WINDOW_ONLY_NOT_MA_SEMANTIC_VALIDATION',
    'source_snapshot_id': verified['snapshot_id'],
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'event_route_catalog_sha256': digest(ROOT/'catalog/event_routes.json'),
    'approved_aliases_inspected_only': aliases,
    'companies': rows,
    'source_log_claims_and_active_unchanged': True,
    'all_801_layouts_proven': False,
    'new_result_or_run_created': False,
    'new_real_calls': [0, 0, 0]}
(HERE/'current-801-census.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'companies': len(rows),
    'eight01_claims': sum(len(row['item_801_claims']) for row in rows),
    'accepted_sections': sum(item['section_status'] == 'BOUND_VISIBLE_SECTION'
        for row in rows for item in row['item_801_claims']),
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
