"""Four current B03 direct-D&A source relations, bounded to saved originals."""

import csv
from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from unittest.mock import patch


CODE_ROOT = Path(__file__).resolve().parents[4]
LEDGER_ROOT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
PROCESSING_PARENT = Path('/private/tmp/issue28-b03-marriott-contract-20260929/sources')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_ROOT / 'scripts'))

from vnext.b03_contract_amortization_scope import assess_current_b03_scope
from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.deterministic_router import _numeric_xbrl_value, parse_accession_xbrl_source
from vnext.normal_run_v3 import prepare_case
from vnext.ordinary_processing_source import current_processing_source
from vnext.requirements import load_requirement_snapshot


CASES = {
    'southwest_airlines': {
        'da_usd': '1560000000',
        'cold': 'ordinary-southwest-current-36-cli-20260929/cold.json',
        'same_statement': r'Depreciation and amortization 1,560 1,657 1,522 '
                          r'Impairment of long-lived assets 8',
        'distinct_reported_item': 'Impairment of long-lived assets 8',
    },
    'lumen_technologies': {
        'da_usd': '2749000000',
        'cold': 'ordinary-lumen-current-36-cli-20260929/cold.json',
        'same_statement': r'Depreciation and amortization 2,749 2,956 2,985 '
                          r'Net loss on sale of businesses — 17 121 '
                          r'Goodwill impairment 628 — 10,693 '
                          r'Impairment of long-lived assets 109 83 27',
        'distinct_reported_item': 'Goodwill impairment 628',
    },
    'macys': {
        'da_usd': '894000000',
        'cold': 'ordinary-macys-current-36-cli-20260929/cold.json',
        'same_statement': r'Impairment, restructuring and other costs 230 171 1,027 '
                          r'Pension settlement charges 67 46 134 '
                          r'Depreciation and amortization 894 881 897',
        'distinct_reported_item': 'Impairment, restructuring and other costs 230',
    },
    'enphase_energy': {
        'da_usd': '80645000',
        'cold': 'ordinary-enphase-current-36-cli-20260929/cold.json',
        'same_statement': r'Depreciation and amortization 80,645 81,389 74,708'
                          r'.{0,300}Asset impairment 3,114 28,843 10,603',
        'distinct_reported_item': 'Asset impairment 3,114',
    },
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original(source_root, url):
    with (source_root / 'evidence/requests_log.csv').open(newline='') as handle:
        matches = [row for row in csv.DictReader(handle)
                   if row['source_url'] == url and row['status_code'] == '200']
    assert matches, url
    row = matches[-1]
    raw = (source_root / row['repo_relative_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['content_sha256']
    return raw, {key: row[key] for key in ('source_url', 'repo_relative_path',
                                          'content_sha256', 'status_code')}


def inspect_one(*, company, expected, source_root, processing_root):
    case = prepare_case(data_root=processing_root, company_id=company,
                        metric_id='B03')
    result = case['results']['B03']
    observation, = [row for row in case['observations']
                    if row['metric_id'] == 'B03'
                    and row['semantic_role'] == 'depreciation_and_amortization']
    assert observation['value'] == expected['da_usd']
    assert result['publication'] == 'PUBLISHED' and result['reason_code'] == 'PASS'
    scope = assess_current_b03_scope(case=case, data_root=processing_root)
    assert scope['status'] == 'NO_EXPLICIT_NARROW_SCOPE_FOUND'
    assert scope['blocked'] is False and scope['complete_depreciation_scope_proven'] is False
    reference, = [row for row in case['references'] if row['source_role'] == 'target_primary'
                  and row['accession'] == observation['source_binding']['accession']]
    raw, row = original(source_root, reference['source_url'])
    assert reference['raw_asset_id'] == 'sha256:' + row['content_sha256']
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    target = case['target_period']
    inline = []
    for fact in parsed.facts:
        if fact['qualified_name'] != observation['source_binding']['concept']:
            continue
        context = parsed.contexts[fact['context_ref']]
        if (context['period_start'], context['period_end']) != (
                target['period_start'], target['period_end']) or \
                context['dimensions'] or context['typed_dimension_count'] or \
                str(int(context['entity_identifier'])) != str(int(
                    observation['source_binding']['entity'])):
            continue
        value = Decimal(str(_numeric_xbrl_value(text=fact['text'],
            scale=fact['scale'], sign=fact['sign'])))
        if value == Decimal(expected['da_usd']):
            inline.append({'ordinal': fact['ordinal'],
                           'context_ref': fact['context_ref'],
                           'value_usd': str(value)})
    assert inline, company
    visible = ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ',
        raw.decode('utf-8-sig'))).split())
    match = re.search(expected['same_statement'], visible)
    assert match is not None and expected['distinct_reported_item'] in match.group(), company
    cold_path = CODE_ROOT / 'docs/evidence/issue28_continuous' / expected['cold']
    cold = json.loads(cold_path.read_text())
    prior, = [row for row in cold['rows'] if row['metric_id'] == 'B03']
    assert prior['result_id'] == result['result_id']
    assert all(prior[key] == result[key] for key in ('value', 'unit', 'quality',
        'publication', 'reason_code', 'period_start', 'period_end'))
    return {'company_id': company, 'source_reference': reference,
        'source_log_row': row, 'selected_da_observation_id': observation['observation_id'],
        'selected_da_usd': observation['value'], 'inline_original_facts': inline,
        'paired_visible_statement_start_char': match.start(),
        'paired_visible_statement_sha256': hashlib.sha256(
            match.group().encode()).hexdigest(),
        'distinct_reported_item': expected['distinct_reported_item'],
        'current_source_guard': scope['status'],
        'complete_da_scope_proven_by_guard': False,
        'result_id_matches_prior_cold_read': result['result_id'],
        'prior_cold_read_sha256': digest(cold_path),
        'formal_adoption': False}


def main():
    source_root = LEDGER_ROOT / 'source-inputs'
    protected = {'claims': LEDGER_ROOT / 'claims.jsonl',
                 'source_log': source_root / 'evidence/requests_log.csv',
                 'active': CODE_ROOT / 'outputs/active_publication.json'}
    before = {key: digest(path) for key, path in protected.items()}
    requirement = load_requirement_snapshot(
        snapshot_dir=CODE_ROOT / 'requirements' / REQUIREMENT_ID)
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')):
        processing = current_processing_source(
            acquisition_root=source_root, output_parent=PROCESSING_PARENT,
            requirement=requirement)
        rows = [inspect_one(company=company, expected=expected,
            source_root=source_root, processing_root=processing['data_root'])
            for company, expected in CASES.items()]
    after = {key: digest(path) for key, path in protected.items()}
    assert before == after
    body = {'record_type': 'ISSUE28_B03_FOUR_DIRECT_SOURCE_RELATION_CHECKS',
        'tested_git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'],
            cwd=CODE_ROOT, text=True).strip(),
        'processing_snapshot_id': processing['snapshot_id'],
        'rows': rows, 'source_log_claims_and_active_unchanged': before == after,
        'new_result_or_run': False, 'new_real_calls': [0, 0, 0],
        'full_b03_semantic_acceptance': False, 'all390_acceptance': False,
        'formal_adoption': False}
    (HERE / 'audit.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    print(json.dumps({'verified_rows': len(rows),
        'companies': [row['company_id'] for row in rows],
        'result_ids_match_prior_cold_reads': True,
        'complete_da_scope_proven': False,
        'protected_hashes_unchanged': before == after,
        'new_real_calls': [0, 0, 0]}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
