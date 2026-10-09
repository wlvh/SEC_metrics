"""Measure response-shape pressure for every current D03 saved-source group.

No response here is a model answer or business verdict. The three generated
shapes only bound structural overhead and illustrate two coverage patterns.
"""
import json
import socket
import time
from pathlib import Path
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.continuous_request_context import _load_tokenizer
from vnext.d03_native_preparation import prepare_native_input
from vnext.normal_annual_input import _registry_rows
from vnext.normal_source_authority import ROOT


HERE = Path(__file__).resolve().parent
PREVIOUS = ROOT / 'docs/evidence/issue28_continuous/d03-current-input-census-20260927/census.json'
MAX_OUTPUT_TOKENS = 4096


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'))


def scenarios(request):
    candidates = {}
    for row in request['required_candidate_assessments']:
        candidates.setdefault(row['unit_id'], []).append(row)
    bare, contextual, enumerated = [], [], []
    for unit in request['units']:
        unit_id = unit['unit_id']
        base = {'unit_id': unit_id, 'reviewed': True,
                'findings': [], 'context_only_source_indices': [],
                'unresolved': []}
        bare.append(base)
        selected = candidates.get(unit_id, [])
        contextual.append({**base, 'context_only_source_indices': sorted({
            item['source_index'] for item in selected})})
        findings = [{'kind': 'OTHER_MEANING', 'subject': 'OTHER_ENTITY',
            'event_dates': [], 'reported_status': 'NOT_AN_ACTION_STATEMENT',
            'evidence': [{'kind': item['kind'],
                          'source_index': item['source_index']}],
            'reason': 'x'} for item in selected]
        enumerated.append({**base, 'findings': findings})
    return {name: {'request_id': request['request_id'], 'units': units}
            for name, units in [('bare_structure', bare),
                                ('all_required_context', contextual),
                                ('one_minimal_finding_per_required', enumerated)]}


def main():
    previous = json.loads(PREVIOUS.read_text())
    before = {row['company_id']: row for row in previous['companies']}
    tokenizer, fallback = _load_tokenizer()
    assert tokenizer is not None and fallback is None
    rows = []
    with original_sources_only(), \
         patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('SEC_HTTP_FORBIDDEN')):
        for company in (row['company_id'] for row in _registry_rows(repo_root=ROOT)):
            start = time.monotonic()
            prepared = prepare_native_input(company_id=company)
            expected = before[company]
            assert prepared['source_id'] == expected['source_id']
            assert len(prepared['groups']) == expected['request_count']
            groups = []
            for group in prepared['groups']:
                request = group['effective_request']
                samples = scenarios(request)
                tokens = {name: len(tokenizer.encode(compact(value),
                    add_special_tokens=False).ids) for name, value in samples.items()}
                needed = request['required_candidate_assessments']
                by_unit = {}
                for item in needed:
                    by_unit[item['unit_id']] = by_unit.get(item['unit_id'], 0) + 1
                groups.append({'group_index': group['group_index'],
                    'request_id': group['effective_request_id'],
                    'source_anchor_successor': group['source_anchor_successor'],
                    'unit_count': len(request['units']),
                    'required_candidate_count': len(needed),
                    'max_required_in_one_unit': max(by_unit.values(), default=0),
                    'scenario_tokens': tokens,
                    'bare_structure_exceeds_4096': tokens['bare_structure'] > MAX_OUTPUT_TOKENS,
                    'context_scenario_exceeds_4096': tokens['all_required_context'] > MAX_OUTPUT_TOKENS,
                    'enumerated_scenario_exceeds_4096': tokens['one_minimal_finding_per_required'] > MAX_OUTPUT_TOKENS})
            row = {'company_id': company, 'source_id': prepared['source_id'],
                'group_count': len(groups), 'groups': groups,
                'elapsed_seconds': round(time.monotonic() - start, 3)}
            rows.append(row)
            print(json.dumps({'company_id': company, 'groups': len(groups),
                'max_required': max(g['required_candidate_count'] for g in groups),
                'max_bare_tokens': max(g['scenario_tokens']['bare_structure'] for g in groups),
                'max_context_tokens': max(g['scenario_tokens']['all_required_context'] for g in groups),
                'max_enumerated_tokens': max(g['scenario_tokens']['one_minimal_finding_per_required'] for g in groups),
                'elapsed_seconds': row['elapsed_seconds']}, sort_keys=True), flush=True)
    all_groups = [group for row in rows for group in row['groups']]
    result = {'record_type': 'D03_SAVED_SOURCE_RESPONSE_SHAPE_CAPACITY_CENSUS',
        'base_census': str(PREVIOUS.relative_to(ROOT)),
        'output_token_limit': MAX_OUTPUT_TOKENS,
        'company_count': len(rows), 'group_count': len(all_groups),
        'companies': rows,
        'groups_over_limit': {key: [g['request_id'] for g in all_groups if g[key]]
            for key in ('bare_structure_exceeds_4096',
                        'context_scenario_exceeds_4096',
                        'enumerated_scenario_exceeds_4096')},
        'actual_model_output_observed': False, 'semantic_correctness_proven': False,
        'native_result_created': False, 'real_calls': [0, 0, 0],
        'new_call_authorization': False}
    assert len(rows) == 10 and len(all_groups) == previous['successful_request_count'] == 130
    temporary = HERE / 'census.json.tmp'
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(HERE / 'census.json')
    print('FINAL', len(rows), len(all_groups),
          {key: len(value) for key, value in result['groups_over_limit'].items()},
          flush=True)


if __name__ == '__main__':
    main()
