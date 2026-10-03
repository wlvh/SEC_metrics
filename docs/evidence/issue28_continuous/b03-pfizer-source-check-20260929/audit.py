"""Read-only, current-code Pfizer B03 source/Result check; no result creation."""

import csv
from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path
import re
import socket
import sys
from unittest.mock import patch


CODE_ROOT = Path(__file__).resolve().parents[4]
LEDGER_ROOT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
PROCESSING_PARENT = Path('/private/tmp/issue28-b03-pfizer-source-check-20260929/sources')
PRIOR_COLD = (CODE_ROOT / 'docs/evidence/issue28_continuous/'
              'ordinary-pfizer-current-36-cli-20260929/cold.json')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_ROOT / 'scripts'))

from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.normal_run_v3 import prepare_case
from vnext.ordinary_processing_source import current_processing_source
from vnext.requirements import load_requirement_snapshot


URL_PREFIX = ('https://www.sec.gov/Archives/edgar/data/78003/'
              '000007800326000026/pfe-20251231')
PERIOD = ('2025-01-01', '2025-12-31')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved_original(source_root, suffix):
    url = URL_PREFIX + suffix
    with (source_root / 'evidence/requests_log.csv').open(newline='') as handle:
        matches = [row for row in csv.DictReader(handle)
                   if row['source_url'] == url and row['status_code'] == '200']
    assert matches, url
    row = matches[-1]
    raw = (source_root / row['repo_relative_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['content_sha256']
    return raw, {key: row[key] for key in ('source_url', 'repo_relative_path',
                                          'content_sha256', 'status_code')}


def native_amounts(raw):
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    desired = {
        'us-gaap:depreciationdepletionandamortization': '6592000000',
        'pfe:assetwriteoffsandassetimpairmentcharges': '5270000000',
        'us-gaap:revenues': '62579000000',
        'us-gaap:othernonoperatingincomeexpense': '-6724000000',
        'us-gaap:incomelossfromcontinuingoperationsbeforeincometaxesextraordinaryitemsnoncontrollinginterest':
            '7520000000',
    }
    found = {key: [] for key in desired}
    current_values = {key: set() for key in desired}
    for fact in parsed.facts:
        key = fact['qualified_name'].casefold()
        if key not in desired:
            continue
        context = parsed.contexts[fact['context_ref']]
        if (context['period_start'], context['period_end']) != PERIOD or \
                context['dimensions'] or context['typed_dimension_count'] or \
                str(int(context['entity_identifier'])) != '78003' or fact['unit_ref'] != 'usd':
            continue
        current_values[key].add(fact['text'])
        if fact['text'] == desired[key]:
            found[key].append({'ordinal': fact['ordinal'],
                               'context_ref': fact['context_ref'],
                               'value_usd': fact['text']})
    assert all(found.values()), {key: len(value) for key, value in found.items()}
    assert current_values == {key: {value} for key, value in desired.items()}, \
        current_values
    return found


def reported_presentation(raw):
    normalized = ' '.join(html.unescape(re.sub(
        r'<[^>]*>', ' ', raw.decode('utf-8-sig'))).split())
    cash = ('Depreciation and amortization 6,592 7,013 6,290 '
            'Asset write-offs and impairments 5,270 4,242 3,408')
    assert normalized.count(cash) == 1
    segment_start = normalized.index('Selected Statement of Operations Information')
    segment_end = normalized.index('(a) Income from continuing operations', segment_start)
    segment = normalized[segment_start:segment_end]
    assert 'Depreciation and Amortization (b)' in segment
    assert segment.count('$ 6,592 $ 7,013 $ 6,290') == 1
    assert all(fragment in segment for fragment in (
        'Biopharma (c) $ 61,199', '1,379 $ 1,360 $ 1,213',
        'Other business activities (d) 1,380', '305 340 323',
        'Amortization of intangible assets ( 4,874 )',
        '4,874 5,286 4,733', 'Acquisition-related items ( 1,285 )',
        '( 4 ) 12 ( 11 )', 'Certain significant items (e) ( 7,464 )',
        '38 14 32'))
    assert 1379 + 305 + 4874 - 4 + 38 == 6592
    return {'normalized_text_sha256': hashlib.sha256(normalized.encode()).hexdigest(),
            'cash_flow_adjacent_row_start_char': normalized.index(cash),
            'cash_flow_reported_da_million_usd': 6592,
            'cash_flow_separately_reported_writeoffs_impairments_million_usd': 5270,
            'segment_table_start_char': segment_start,
            'segment_da_components_million_usd': [1379, 305, 4874, -4, 38],
            'segment_da_total_million_usd': 6592}


def main():
    source_root = LEDGER_ROOT / 'source-inputs'
    protected = {'claims': LEDGER_ROOT / 'claims.jsonl',
                 'source_log': source_root / 'evidence/requests_log.csv',
                 'active': CODE_ROOT / 'outputs/active_publication.json'}
    before = {key: digest(value) for key, value in protected.items()}
    requirement = load_requirement_snapshot(
        snapshot_dir=CODE_ROOT / 'requirements' / REQUIREMENT_ID)
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')):
        processing = current_processing_source(
            acquisition_root=source_root,
            output_parent=PROCESSING_PARENT, requirement=requirement)
        case = prepare_case(data_root=processing['data_root'],
                            company_id='pfizer', metric_id='B03')
    result = case['results']['B03']
    original = {row['semantic_role']: row for row in case['observations']
                if row['metric_id'] == 'B03'}
    assert {key: original[key]['value'] for key in (
        'pretax', 'nonoperating', 'depreciation_and_amortization')} == {
            'pretax': '7520000000', 'nonoperating': '-6724000000',
            'depreciation_and_amortization': '6592000000'}
    assert case['results']['B01']['value'] == '62579000000'
    computed = ((Decimal('7520000000') - Decimal('-6724000000')
                + Decimal('6592000000')) / Decimal('62579000000'))
    assert Decimal(result['value']) == computed
    primary, primary_ref = saved_original(source_root, '.htm')
    xml, xml_ref = saved_original(source_root, '_htm.xml')
    facts = native_amounts(xml)
    presentation = reported_presentation(primary)
    previous = json.loads(PRIOR_COLD.read_text())
    previous_result, = [row for row in previous['rows']
                        if row['metric_id'] == 'B03']
    assert previous_result['status'] == 'CANDIDATE_READY'
    after = {key: digest(value) for key, value in protected.items()}
    assert before == after
    body = {'record_type': 'ISSUE28_PFIZER_B03_BOUND_CURRENT_SOURCE_CHECK',
            'tested_code_head': __import__('subprocess').check_output(
                ['git', 'rev-parse', 'HEAD'], cwd=CODE_ROOT, text=True).strip(),
            'processing_snapshot_id': processing['snapshot_id'],
            'processing_copy_reused': processing['reused'],
            'source_references': [primary_ref, xml_ref],
            'native_current_annual_undimensioned_facts': facts,
            'reported_presentation': presentation,
            'current_result': {key: result[key] for key in (
                'result_id', 'value', 'unit', 'quality', 'publication', 'reason_code',
                'period_start', 'period_end', 'spec_closure_hash')},
            'previous_cold_read_sha256': digest(PRIOR_COLD),
            'previous_result_id': previous_result['result_id'],
            'previous_result_business_fields_equal': all(result[key] == previous_result[key]
                for key in ('result_id', 'value', 'unit', 'quality', 'publication',
                            'reason_code', 'period_start', 'period_end')),
            'original_protected_hashes_unchanged': before == after,
            'new_real_calls': [0, 0, 0],
            'formal_adoption': False, 'all390_acceptance': False}
    (HERE / 'audit.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    print(json.dumps({'current_result_id': result['result_id'],
        'previous_result_id': previous_result['result_id'],
        'business_fields_equal': body['previous_result_business_fields_equal'],
        'source_hashes_valid': True, 'originals_unchanged': before == after,
        'new_real_calls': [0, 0, 0]}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
