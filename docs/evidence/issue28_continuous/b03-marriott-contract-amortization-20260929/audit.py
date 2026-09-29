"""Bounded original-source check for the Marriott FY2025 B03 D&A relation."""

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
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.normal_run_v3 import prepare_case
from vnext.ordinary_processing_source import current_processing_source
from vnext.requirements import load_requirement_snapshot


SOURCE_PREFIX = ('https://www.sec.gov/Archives/edgar/data/1048286/'
                 '000104828626000007/mar-20251231')
AMOUNTS = {
    2025: {'depreciation': 145, 'depreciation_reimbursed': 39,
           'intangible_amortization': 313, 'amortization_reimbursed': 206,
           'contract_amortization': 135, 'operating_da': 213, 'cash_flow_da_and_other': 599},
    2024: {'depreciation': 128, 'depreciation_reimbursed': 42,
           'intangible_amortization': 255, 'amortization_reimbursed': 158,
           'contract_amortization': 103, 'operating_da': 183, 'cash_flow_da_and_other': 492},
    2023: {'depreciation': 122, 'depreciation_reimbursed': 37,
           'intangible_amortization': 226, 'amortization_reimbursed': 122,
           'contract_amortization': 88, 'operating_da': 189, 'cash_flow_da_and_other': 436},
}
CONCEPTS = {
    'depreciation': 'us-gaap:depreciation',
    'depreciation_reimbursed': 'us-gaap:depreciation',
    'intangible_amortization': 'us-gaap:amortizationofintangibleassets',
    'amortization_reimbursed': 'us-gaap:amortizationofintangibleassets',
    'contract_amortization': 'us-gaap:capitalizedcontractcostamortization',
    'operating_da': 'mar:depreciationamortizationandotherexcludingcapitalizedcontractcostamortization',
    'cash_flow_da_and_other': 'mar:depreciationamortizationandother',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original(source_root, suffix):
    url = SOURCE_PREFIX + suffix
    with (source_root / 'evidence/requests_log.csv').open(newline='') as handle:
        rows = [row for row in csv.DictReader(handle)
                if row['source_url'] == url and row['status_code'] == '200']
    assert rows, url
    row = rows[-1]
    raw = (source_root / row['repo_relative_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['content_sha256']
    return raw, {key: row[key] for key in ('source_url', 'repo_relative_path',
                                          'content_sha256', 'status_code')}


def fact_rows(xml):
    parsed = parse_accession_xbrl_source(raw_bytes=xml)
    values = {}
    for year, expected in AMOUNTS.items():
        start, end = f'{year}-01-01', f'{year}-12-31'
        values[str(year)] = {}
        for role, million in expected.items():
            matches = []
            for fact in parsed.facts:
                if fact['qualified_name'].casefold() != CONCEPTS[role]:
                    continue
                context = parsed.contexts[fact['context_ref']]
                if (context['period_start'], context['period_end']) != (start, end) or \
                        str(int(context['entity_identifier'])) != '1048286' or \
                        context['typed_dimension_count'] or fact['unit_ref'] != 'usd':
                    continue
                dimensions = dict(context['dimensions'])
                if role == 'depreciation_reimbursed':
                    allowed = {'us-gaap:IncomeStatementLocationAxis':
                               'mar:ReimbursedCostsMember'}
                elif role == 'amortization_reimbursed':
                    allowed = {'us-gaap:IncomeStatementLocationAxis':
                               'mar:ReimbursedExpensesMember'}
                elif role == 'contract_amortization':
                    allowed = {'srt:ProductOrServiceAxis': 'mar:FeeServiceMember'}
                else:
                    allowed = {}
                if dimensions != allowed or fact['text'] in {'—', '-'}:
                    continue
                actual = Decimal(fact['text'].replace(',', '')) * (Decimal(10) ** int(fact['scale']))
                if fact['sign'] == '-':
                    actual = -actual
                if actual == Decimal(million) * 1000000:
                    matches.append({'ordinal': fact['ordinal'],
                                    'value_usd': str(actual),
                                    'context_ref': fact['context_ref'],
                                    'dimensions': dimensions})
            assert matches, (year, role, million)
            values[str(year)][role] = matches
    return values


def visible_relationship(primary):
    text = ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ',
        primary.decode('utf-8-sig'))).split())
    phrases = {
        'income_statement': 'Contract investment amortization ( 135 ) ( 103 ) ( 88 ) Net fee revenues',
        'operating_statement': 'Depreciation, amortization, and other 213 183 189',
        'cash_flow': ('Depreciation, amortization, and other (including depreciation '
                      'and amortization classified in reimbursed expenses) (2) 599 492 436'),
        'intangible_total': 'recorded amortization expense of $ 313 million in 2025',
        'intangible_reimbursed': 'of which $ 206 million in 2025',
        'depreciation_total': 'gross depreciation expense totaled $ 145 million in 2025',
        'depreciation_reimbursed': 'of which $ 39 million in 2025',
        'contract_location': ('related amortization in the “Contract investment '
                              'amortization” caption of our Income Statements'),
    }
    offsets = {}
    for key, phrase in phrases.items():
        assert text.count(phrase) >= 1, key
        offsets[key] = text.index(phrase)
    # The two parentheticals are subsets of the gross D&A amounts, whereas
    # contract-investment amortization appears as a separate revenue reduction.
    assert offsets['intangible_total'] < offsets['intangible_reimbursed']
    assert offsets['depreciation_total'] < offsets['depreciation_reimbursed']
    return {'normalized_visible_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'reported_phrase_start_chars': offsets}


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
        case = prepare_case(data_root=processing['data_root'],
                            company_id='marriott_international', metric_id='B03')
        guard = assess_current_b03_scope(
            case=case, data_root=processing['data_root'])
    assert guard['status'] == 'COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED'
    assert guard['blocked'] and not guard['amount_added_or_result_recomputed']
    assert guard['selected_components'] == {'depreciation': '145000000',
                                             'amortization': '313000000'}
    assert any(row['value_usd'] == '135000000' and row['dimensions'] == {
        'srt:ProductOrServiceAxis': 'mar:FeeServiceMember'}
        for row in guard['additional_facts'])
    primary, primary_ref = original(source_root, '.htm')
    xml, xml_ref = original(source_root, '_htm.xml')
    amounts = fact_rows(xml)
    visible = visible_relationship(primary)
    reconciliations = {}
    for year, row in AMOUNTS.items():
        other = row['cash_flow_da_and_other'] - (row['depreciation'] +
            row['intangible_amortization'] + row['contract_amortization'])
        assert ((row['depreciation'] - row['depreciation_reimbursed']) +
            (row['intangible_amortization'] - row['amortization_reimbursed'])
            == row['operating_da'])
        assert other == (6 if year in (2024, 2025) else 0)
        reconciliations[str(year)] = {'reported_million_usd': row,
            'cash_flow_other_residual_million_usd': other}
    result = case['results']['B03']
    assert result['result_id'] == ('sha256:3043aa63cbf7616f9866fb93b8f69200'
                                   'a2246a33dfec8f1d09502a34af39a72a')
    assert result['value'] == '0.1756281982738868097456656229'
    assert result['quality'] == 'EXACT' and result['publication'] == 'PUBLISHED'
    index_path = (CODE_ROOT / 'docs/evidence/issue28_continuous/'
        'd04-remaining-20260922/current-390.json')
    indexed = json.loads(index_path.read_text())
    old, = [row for row in indexed['rows'] if row['company_id'] ==
            'marriott_international' and row['metric_id'] == 'B03']
    assert old['implementation_identity']['result_id'] == result['result_id']
    assert old['value'] == result['value']
    after = {key: digest(path) for key, path in protected.items()}
    assert before == after
    tested_files = (
        'scripts/vnext/b03_contract_amortization_scope.py',
        'scripts/vnext/ordinary_b03_scope_update.py',
        'scripts/vnext/ordinary_release_preparation.py',
        'scripts/vnext/ordinary_isolated_publication.py',
        'requirements/issue_28_v14/baseline_manifest.json',
    )
    body = {'record_type': 'ISSUE28_MARRIOTT_B03_CONTRACT_AMORTIZATION_SCOPE_AUDIT',
        'base_git_head_before_uncommitted_patch': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=CODE_ROOT, text=True).strip(),
        'tested_worktree_included_uncommitted_product_diff': True,
        'tested_runtime_sha256': {path: digest(CODE_ROOT / path)
                                  for path in tested_files},
        'processing_snapshot_id': processing['snapshot_id'],
        'source_references': [primary_ref, xml_ref],
        'native_facts_by_year': amounts,
        'visible_relationship': visible,
        'reconciliations': reconciliations,
        'current_result_id_retained_without_current_credit': result['result_id'],
        'current_result_value_retained_without_current_credit': result['value'],
        'current_scope_guard': guard,
        'current_390_index_unchanged': True,
        'source_log_claims_and_active_unchanged': before == after,
        'new_real_calls': [0, 0, 0], 'new_result_or_run': False,
        'formal_adoption': False, 'all390_acceptance': False}
    (HERE / 'audit.json').write_text(json.dumps(body, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    delta = {'record_type': 'ISSUE28_CURRENT_390_ONE_COORDINATE_SCOPE_DELTA',
        'parent_index_sha256': digest(index_path),
        'company_id': 'marriott_international', 'metric_id': 'B03',
        'historical_result_id_retained': result['result_id'],
        'historical_value_retained': result['value'],
        'current_business_credit': 'WITHHELD_IMPLEMENTATION_SCOPE_UNRESOLVED',
        'current_value_asserted': None,
        'reason': guard['status'],
        'new_result_or_run': False, 'new_real_calls': [0, 0, 0],
        'parent_index_modified': False, 'production_authorized': False}
    (HERE / 'delta.json').write_text(json.dumps(delta, ensure_ascii=False,
        indent=2, sort_keys=True) + '\n')
    print(json.dumps({'guard_status': guard['status'],
        'selected_da_million_usd': 458,
        'additional_contract_amortization_million_usd': 135,
        'current_result_id_retained': result['result_id'],
        'originals_unchanged': before == after,
        'new_real_calls': [0, 0, 0]}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
