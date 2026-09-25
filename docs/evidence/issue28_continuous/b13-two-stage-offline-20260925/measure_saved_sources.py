"""Read-only B13 source and request-shape comparison; never enters transport."""
import argparse
import json
import math
from pathlib import Path
from types import SimpleNamespace

from vnext.capacity_reference_contract import upgrade_request
from vnext.capacity_semantic_review import requests_from_source
from vnext.capacity_two_stage import (
    MAX_CANDIDATE_REFS, _reference_inventory, _required_references,
    interpretation_request, scan_request, validate_scan,
)
from vnext.canonical import canonical_json_bytes, strict_json_file
from vnext.continuous_request_context import measure_request
from vnext.continuous_semantic_calls import request_body


def measure(request):
    result = measure_request(request_body(request, SimpleNamespace(model='deepseek-flash')),
                             require_reference=True)
    return {key: result[key] for key in ('input_tokens', 'context_tokens', 'fits',
                                         'request_bytes', 'request_sha256')}


def run(ledger_root):
    results = []
    for ordinal in (190, 171):
        source = strict_json_file(path=ledger_root/'calls'/f'{ordinal:04d}'/'source.json')
        base = requests_from_source(source)
        company = source['company_id']
        groups = []
        for index, original in enumerate(base):
            visible = [len(unit['payload']['blocks']) for unit in original['units']
                       if unit['kind'] == 'VISIBLE_TEXT']
            native = sum(unit['kind'] != 'VISIBLE_TEXT' for unit in original['units'])
            option_a = sum(math.ceil(count / 128) for count in visible) + (1 if native else 0)
            row = {'group_index': index, 'original_units': len(original['units']),
                   'visible_block_counts': visible, 'native_unit_count': native,
                   'required_candidate_count': len(original['required_candidate_assessments']),
                   'option_a_illustrative_128_block_requests': option_a,
                   'original_input': measure(original)}
            if company == 'enphase_energy' and index == 0:
                row['decision'] = 'KEEP_190_EXACT_SUCCESS_AND_REPLAY'; groups.append(row); continue
            v4 = upgrade_request(original, compact=True, role_labels=True,
                                 relevance_scope=True)
            scan = scan_request(v4)
            inventory = _reference_inventory(v4)
            required = _required_references(v4, inventory)
            candidates = list(sorted(required)) + [ref for ref in inventory
                if ref not in required][:MAX_CANDIDATE_REFS-len(required)]
            response = {'units_reviewed': list(range(len(v4['units']))),
                        'candidate_refs': candidates, 'unresolved_refs': []}
            scan_result = validate_scan(request=v4, scan_request_value=scan,
                raw_response=canonical_json_bytes(value=response))
            assessment = interpretation_request(request=v4,
                                                scan_result=scan_result)
            row.update(option_b_scan_input=measure(scan),
                       option_b_assessment_input_at_64_refs=measure(assessment),
                       option_b_synthetic_ref_count=len(candidates),
                       option_b_existing_units_unchanged=(scan['units'] == v4['units']
                                                           == assessment['units']),
                       option_b_max_requests_for_group=2,
                       option_b_no_model_relevance_proof=True)
            groups.append(row)
        results.append({'company_id': company, 'saved_ordinal': ordinal,
                        'source_id': source['semantic_source_id'],
                        'source_unit_count': len(source['units']),
                        'original_group_count': len(base), 'groups': groups,
                        'option_a_illustrative_new_calls': sum(
                            row['option_a_illustrative_128_block_requests'] for row in groups
                            if row.get('decision') is None),
                        'option_b_max_new_calls': sum(row.get('option_b_max_requests_for_group', 0)
                                                      for row in groups)})
    return {'record_type': 'ISSUE28_B13_SAVED_SOURCE_TASK_COMPARISON',
            'read_only': True, 'real_model_calls': 0, 'sec_calls': 0,
            'output_limit_tokens': 4096, 'max_candidate_refs_per_original_group': MAX_CANDIDATE_REFS,
            'option_a_128_block_count_is_illustrative_not_request_validation': True,
            'option_b_64_refs_are_synthetic_capacity_stress_not_model_findings': True,
            'companies': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.ledger_root)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'calls': [(row['company_id'], row['option_a_illustrative_new_calls'],
                                 row['option_b_max_new_calls']) for row in result['companies']],
                      'all_stage_inputs_fit': all(
                          item['option_b_scan_input']['fits'] and
                          item['option_b_assessment_input_at_64_refs']['fits']
                          for company in result['companies'] for item in company['groups']
                          if 'option_b_scan_input' in item)}))
