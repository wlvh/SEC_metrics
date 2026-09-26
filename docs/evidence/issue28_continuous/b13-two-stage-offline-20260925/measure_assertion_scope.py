"""Read-only V6 request sizing over original Enphase/Ford saved groups."""
import argparse
import json
from pathlib import Path
import random
import string
from types import SimpleNamespace

from vnext.capacity_reference_contract import upgrade_request
from vnext.capacity_semantic_review import requests_from_source
from vnext.capacity_two_stage import (MAX_ASSERTION_SCOPED_REFS,
    MAX_ASSERTION_SCOPED_FINDINGS, _program_owned_references,
    _reference_inventory, _required_references,
    interpretation_request, scan_request, validate_scan)
from vnext.canonical import (canonical_json_bytes, content_hash,
                             sha256_bytes, strict_json_file)
from vnext.continuous_request_context import _load_tokenizer, measure_request
from vnext.continuous_semantic_calls import request_body


def measure(request):
    result = measure_request(request_body(request,
        SimpleNamespace(model='deepseek-flash')), require_reference=True)
    return {key: result[key] for key in ('input_tokens', 'context_tokens',
        'fits', 'request_bytes', 'request_sha256')}


def upper_example(tokenizer, unit_count):
    randomizer = random.Random(2806)
    alphabet = string.ascii_letters + string.digits
    reason = ''.join(randomizer.choice(alphabet) for _ in range(128))
    response = {'units': [{'unit_index': index, 'reviewed': True,
        'unresolved': [], 'calculation_limits': []}
        for index in range(unit_count)],
        'findings': [['other_context', 0, 0, ['B1234'], reason,
                      [['B1234', 0, 100]]]
                     for _ in range(MAX_ASSERTION_SCOPED_FINDINGS)]}
    raw = canonical_json_bytes(value=response)
    return {'example_bytes': len(raw),
            'example_tokens': len(tokenizer.encode(raw.decode(),
                              add_special_tokens=False).ids),
            'example_not_absolute_maximum': True}


def run(ledger_root):
    tokenizer, error = _load_tokenizer()
    assert tokenizer is not None, error
    companies = []
    for ordinal in (190, 171):
        source = strict_json_file(path=ledger_root/'calls'/f'{ordinal:04d}'/'source.json')
        groups = []
        for index, original in enumerate(requests_from_source(source)):
            if ordinal == 190 and index == 0:
                groups.append({'group_index': index, 'status': 'KEEP_190_ORIGINAL'})
                continue
            prior = upgrade_request(original, compact=True,
                role_labels=True, relevance_scope=True)
            inventory = _reference_inventory(prior)
            required = _required_references(prior, inventory)
            owned = _program_owned_references(prior, inventory)
            remaining = sorted(required - owned)
            assert len(remaining) <= MAX_ASSERTION_SCOPED_REFS
            candidates = remaining + [ref for ref in inventory
                if ref not in required and ref not in owned][
                    :MAX_ASSERTION_SCOPED_REFS-len(remaining)]
            scan = scan_request(prior)
            raw = canonical_json_bytes(value={
                'units_reviewed': list(range(len(prior['units']))),
                'candidate_refs': candidates, 'unresolved_refs': candidates})
            result = validate_scan(request=prior,
                scan_request_value=scan, raw_response=raw)
            proof_body = {'record_type': 'B13_SCAN_STAGE_EXECUTION_PROOF',
                'scan_ordinal': 240, 'scan_request_id': scan['request_id'],
                'scan_result_id': result['scan_result_id'],
                'scan_terminal_id': content_hash(value='synthetic sizing terminal'),
                'scan_acceptance_receipt_id': content_hash(value='synthetic sizing receipt'),
                'scan_output_sha256': sha256_bytes(content=raw),
                'source_id': prior['source_id']}
            scoped = interpretation_request(request=prior,
                scan_result=result, scan_raw_response=raw,
                scan_execution_proof={**proof_body,
                    'proof_id': content_hash(value=proof_body)},
                assertion_scopes=True)
            groups.append({'group_index': index,
                'source_units_unchanged': scoped['units'] == scan['units'] == prior['units'],
                'required_refs': len(remaining),
                'synthetic_refs': len(candidates),
                'scan_input': measure(scan),
                'scoped_interpretation_input': measure(scoped),
                'output_example': upper_example(tokenizer, len(prior['units']))})
        companies.append({'company_id': source['company_id'],
            'saved_ordinal': ordinal, 'source_id': source['semantic_source_id'],
            'groups': groups})
    return {'record_type': 'B13_ASSERTION_SCOPED_SAVED_SOURCE_SIZING',
        'read_only': True, 'real_calls': [0, 0, 0],
        'maximum_candidate_refs_per_group': MAX_ASSERTION_SCOPED_REFS,
        'maximum_findings_per_interpretation': MAX_ASSERTION_SCOPED_FINDINGS,
        'provider_output_limit_tokens': 4096,
        'scope': ('Worst-case-like high-entropy 128-character reason example is '
                  'a size sample, not an absolute token bound or model-success '
                  'proof. Scan uncertainty and a synthetic execution proof '
                  'are included in interpretation request sizing.'),
        'companies': companies}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = run(args.ledger_root)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'all_inputs_fit': all(group['scan_input']['fits'] and
          group['scoped_interpretation_input']['fits']
          for company in value['companies'] for group in company['groups']
          if group.get('status') is None),
          'max_output_example_tokens': max(group['output_example']['example_tokens']
          for company in value['companies'] for group in company['groups']
          if group.get('status') is None)}))
