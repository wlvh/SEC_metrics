"""Map three peer-reported current D02 false selections to #28 Result IDs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CASES = {
    'pfizer': {
        'indexes': (2175, 2240),
        'peer_defect_id': 'D02_PFIZER_2025_SCOPE_CONTENT_READ',
        'reasons': {
            2175: 'An estimates/assumptions policy lists litigation among business risks; it reports no specific proceeding.',
            2240: 'A trade-receivables reserve and collection policy mentions litigation as a possible collection method, not a current case.',
        },
    },
    'paramount_skydance_paramount_global': {
        'indexes': (2257,),
        'peer_defect_id': 'D02_PARAMOUNT_2025_KEYWORD_PROXY_ADMITS_COST_AND_COVENANT_NOTES',
        'reasons': {
            2257: 'A credit-facility leverage covenant names litigation reserves only as one possible EBITDA add-back.',
        },
    },
    'enphase_energy': {
        'indexes': (755,),
        'peer_defect_id': 'D02_ENPHASE_2025_PAGE_FOOTER_CARRIES_ITS_PAGE_NUMBER',
        'reasons': {755: 'A page footer with company name, form and page number is document furniture, not a proceeding disclosure.'},
    },
}
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/claims.jsonl')
SOURCE_LOG = ROOT / 'evidence/requests_log.csv'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def records_for(company):
    state = (Path('/private/tmp') / ('issue28-' + company + '-current-36-cli-20260929') /
             'state' / company / 'metrics/D02/attempts')
    records = list(state.glob('*/runs/D02/records.jsonl'))
    assert len(records) == 1, (company, records)
    return records[0]


before = {'ledger': sha(LEDGER.read_bytes()), 'source_log': sha(SOURCE_LOG.read_bytes())}
assert '# Litigation source disclosures' in (ROOT / 'catalog/r6/D02_legal_disclosures_v1.md').read_text()
outputs = []
for company, rule in CASES.items():
    records_path = records_for(company)
    records = [json.loads(line) for line in records_path.read_text().splitlines()]
    candidate = next(row for row in records if row['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
    evidence = next(row for row in records if row['record_type'] == 'EVIDENCE_CHECK')
    result = next(row for row in records if row['record_type'] == 'METRIC_RESULT'
                  and row['metric_id'] == 'D02')
    manifest = json.loads((records_path.parent / 'manifest.json').read_text())
    comparison_path = (ROOT / 'docs/evidence/issue28_continuous' /
                       ('ordinary-' + ('paramount' if company.startswith('paramount') else
                                       'enphase' if company.startswith('enphase') else company) +
                        '-current-36-cli-20260929/comparison.json'))
    comparison = json.loads(comparison_path.read_text())
    prior = next(row for row in comparison['rows'] if row['metric_id'] == 'D02')
    assert prior['historical_result_id'] == prior['current_result_id'] == result['result_id']
    assert evidence['status'] == 'PASS'
    references = {row['source_reference_id']: row for row in records
                  if row['record_type'] == 'SOURCE_REFERENCE'}
    blobs = {row['raw_asset_id']: row for row in records
             if row['record_type'] == 'RAW_BLOB'}
    bad = []
    for index in rule['indexes']:
        selected = [(role, claim) for role, claim in candidate['selected'].items()
                    if claim['block_index'] == index]
        assert len(selected) == 1, (company, index)
        role, claim = selected[0]
        check = next(check for check in evidence['checks']
                     if check['check'] == 'TEXT_EXACT_EXCERPT:' + role)
        assert check['status'] == 'PASS' and claim['text'] in result['value']
        reference = references[claim['source_reference_id']]
        blob = blobs[reference['raw_asset_id']]
        raw = (records_path.parents[2] / 'data' / blob['storage_uri']).read_bytes()
        assert sha(raw) == blob['raw_asset_id'].removeprefix('sha256:')
        assert len(raw) == blob['byte_length']
        assert sha(raw[claim['raw_start_byte']:claim['raw_end_byte']]) == claim['raw_span_sha256'].removeprefix('sha256:')
        bad.append({'block_index': index, 'role': role, 'section_id': claim['section_id'],
                    'accession': reference['accession'],
                    'source_reference_id': reference['source_reference_id'],
                    'source_raw_asset_id': blob['raw_asset_id'],
                    'raw_span_sha256': claim['raw_span_sha256'],
                    'text_sha256': sha(claim['text'].encode('utf-8')),
                    'text': claim['text'], 'why_out_of_scope': rule['reasons'][index]})
    note = None
    if company.startswith('paramount'):
        valid = next(claim for claim in candidate['selected'].values()
                     if claim['block_index'] == 2108)
        assert 'benefit of $156 million, principally associated with stockholder litigation' in valid['text']
        note = {'block_index': 2108,
                'not_withdrawn_as_false_selection': True,
                'reason': 'The last sentence describes a specific $156 million stockholder-litigation benefit, despite transaction-cost context.'}
    outputs.append({'company_id': company, 'metric_id': 'D02',
                    'period_start': result['period_start'], 'period_end': result['period_end'],
                    'result_id': result['result_id'], 'run_id': manifest['run_id'],
                    'private_quality': result['quality'],
                    'historical_index_same_result_id': True,
                    'candidate_selected_count': len(candidate['selected']),
                    'confirmed_false_selected_blocks': bad,
                    'context_not_retracted': note,
                    'peer_lead': {'fixed_commit': '1f3f446c1d3eb299b95c03ec967a4a5224523353',
                                  'defect_id': rule['peer_defect_id'],
                                  'not_peer_acceptance_credit': True},
                    'old_run_result_source_preserved': True,
                    'current_business_credit': False,
                    'current_390_credit': False})
    print(json.dumps({'company': company, 'result_id': result['result_id'],
                      'wrong_blocks': list(rule['indexes']),
                      'selected_count': len(candidate['selected'])}, sort_keys=True), flush=True)
after = {'ledger': sha(LEDGER.read_bytes()), 'source_log': sha(SOURCE_LOG.read_bytes())}
assert before == after
body = {'record_type': 'ISSUE28_D02_THREE_CURRENT_EXACT_RESULT_DEFECTS',
        'status': 'THREE_CONFIRMED_OUT_OF_SCOPE_SETS_WITH_EXACT_OWN_RESULT_IDENTITIES',
        'rows': outputs, 'original_ledger_and_source_log_unchanged': True,
        'new_real_calls': [0, 0, 0],
        'scope_limit': 'Only the named false excerpts and three exact current Result identities; no full D02 content audit, semantic repair or finding against other companies.'}
(HERE / 'audit.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
